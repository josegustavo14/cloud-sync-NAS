import hmac
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import Settings
from .db import Database, now
from .engine import Engine
from .providers import ProviderError, build_provider, remotes
from .oauth import OAuthError, OAuthWizard
from .update import latest


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: Literal['google_drive', 'onedrive', 'dropbox', 'filesystem', 'takeout']
    location: str = Field(min_length=1, max_length=2048)
    interval_minutes: int = Field(default=360, ge=0, le=525600)


class AccountUpdate(BaseModel):
    enabled: Optional[bool] = None
    interval_minutes: Optional[int] = Field(default=None, ge=0, le=525600)


def create_app(settings=None, background=True):
    settings = settings or Settings.from_env()
    settings.prepare()
    db = Database(settings.root / 'database/cloudsync.sqlite3')
    db.migrate()
    engine = Engine(db, settings)
    oauth = OAuthWizard(settings.root / 'config/rclone.conf')

    @asynccontextmanager
    async def lifespan(app):
        if background:
            engine.start()
        yield
        engine.close()

    app = FastAPI(title='Personal Cloud Sync', version='0.2.0', lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.db, app.state.engine = db, engine

    def authorize(authorization: str = Header(default='')):
        if not hmac.compare_digest(authorization, f'Bearer {settings.token}'):
            raise HTTPException(401, 'Authentication required', headers={'WWW-Authenticate': 'Bearer'})

    protected = [Depends(authorize)]

    @app.get('/health')
    def health():
        db.one('SELECT 1')
        return {'status': 'ok', 'version': app.version}

    @app.get('/api/dashboard', dependencies=protected)
    def dashboard():
        usage = shutil.disk_usage(settings.root)
        return {
            'status': 'ok', 'version': app.version,
            'storage': {'total': usage.total, 'used': usage.used, 'free': usage.free},
            'accounts': db.one('SELECT COUNT(*) n FROM accounts WHERE enabled=1')['n'],
            'files': db.one('SELECT COUNT(*) n FROM blobs')['n'],
            'origins': db.one('SELECT COUNT(*) n FROM origins')['n'],
            'stored_bytes': db.one('SELECT COALESCE(SUM(size),0) n FROM blobs')['n'],
            'last_sync': db.one("SELECT MAX(finished_at) value FROM jobs WHERE status='completed'")['value'],
            'next_sync': db.one('SELECT MIN(next_sync) value FROM accounts WHERE enabled=1')['value'],
            'active_jobs': db.all("SELECT j.*, a.name account_name FROM jobs j JOIN accounts a ON a.id=j.account_id WHERE status IN ('started','running')"),
            'recent_errors': db.all("SELECT * FROM events WHERE level='error' ORDER BY id DESC LIMIT 10"),
        }

    @app.get('/api/accounts', dependencies=protected)
    def accounts():
        return db.all('SELECT * FROM accounts ORDER BY id')

    @app.post('/api/accounts', dependencies=protected, status_code=201)
    def add_account(body: AccountCreate):
        try:
            build_provider(body.model_dump(), settings)
        except ProviderError as exc:
            raise HTTPException(400, str(exc)) from None
        next_sync = (datetime.now(timezone.utc) + timedelta(minutes=body.interval_minutes)).isoformat() if body.interval_minutes else None
        account_id = db.execute('INSERT INTO accounts(name,provider,location,interval_minutes,next_sync,created_at) VALUES(?,?,?,?,?,?)',
                                (body.name, body.provider, body.location, body.interval_minutes, next_sync, now()))
        return db.one('SELECT * FROM accounts WHERE id=?', (account_id,))

    @app.patch('/api/accounts/{account_id}', dependencies=protected)
    def update_account(account_id: int, body: AccountUpdate):
        account = db.one('SELECT * FROM accounts WHERE id=?', (account_id,))
        if not account:
            raise HTTPException(404, 'Account not found')
        enabled = body.enabled if body.enabled is not None else account['enabled']
        interval = body.interval_minutes if body.interval_minutes is not None else account['interval_minutes']
        next_sync = (datetime.now(timezone.utc) + timedelta(minutes=interval)).isoformat() if interval and enabled else None
        db.execute('UPDATE accounts SET enabled=?, interval_minutes=?, next_sync=? WHERE id=?', (enabled, interval, next_sync, account_id))
        if not enabled:
            db.execute("UPDATE jobs SET cancel_requested=1 WHERE account_id=? AND status IN ('started','running')", (account_id,))
        return db.one('SELECT * FROM accounts WHERE id=?', (account_id,))

    @app.delete('/api/accounts/{account_id}', dependencies=protected)
    def remove_account(account_id: int):
        # Archive the integration; preserve all origins, jobs and physical files.
        return update_account(account_id, AccountUpdate(enabled=False))

    @app.post('/api/accounts/{account_id}/sync', dependencies=protected, status_code=202)
    def sync_account(account_id: int):
        try:
            return {'job_id': engine.submit(account_id)}
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.post('/api/sync', dependencies=protected, status_code=202)
    def sync_all():
        return {'job_ids': [engine.submit(a['id']) for a in db.all('SELECT id FROM accounts WHERE enabled=1')]}

    @app.get('/api/jobs', dependencies=protected)
    def jobs(account_id: Optional[int] = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
        return db.all('SELECT j.*,a.name account_name,a.provider FROM jobs j JOIN accounts a ON a.id=j.account_id WHERE (? IS NULL OR account_id=?) ORDER BY j.id DESC LIMIT ? OFFSET ?', (account_id, account_id, limit, offset))

    @app.post('/api/jobs/{job_id}/cancel', dependencies=protected)
    def cancel_job(job_id: int):
        if not db.one('SELECT id FROM jobs WHERE id=?', (job_id,)):
            raise HTTPException(404, 'Job not found')
        db.execute("UPDATE jobs SET cancel_requested=1 WHERE id=? AND status IN ('started','running')", (job_id,))
        return {'ok': True}

    @app.get('/api/jobs/{job_id}/logs', dependencies=protected)
    def logs(job_id: int, after: int = Query(0, ge=0)):
        return db.all('SELECT * FROM events WHERE job_id=? AND id>? ORDER BY id LIMIT 500', (job_id, after))

    @app.get('/api/files', dependencies=protected)
    def files(q: str = '', provider: str = '', account_id: Optional[int] = None,
              extension: str = '', sha256: str = '', original_path: str = '',
              limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
        where = '''WHERE (o.name LIKE ? OR o.original_path LIKE ? OR o.sha256 LIKE ?)
            AND (?='' OR a.provider=?) AND (? IS NULL OR o.account_id=?)
            AND o.name LIKE ? AND o.sha256 LIKE ? AND o.original_path LIKE ?'''
        args = (f'%{q}%', f'%{q}%', f'%{q}%', provider, provider, account_id, account_id,
                f'%.{extension.lstrip(".")}' if extension else '%', f'{sha256}%', f'%{original_path}%')
        joins = ' FROM origins o JOIN accounts a ON a.id=o.account_id JOIN blobs b ON b.sha256=o.sha256 '
        return {'total': db.one('SELECT COUNT(*) n' + joins + where, args)['n'],
                'items': db.all('SELECT o.*,a.name account_name,a.provider,b.local_path' + joins + where + ' ORDER BY o.id DESC LIMIT ? OFFSET ?', args + (limit, offset))}

    @app.get('/api/files/{sha256}/origins', dependencies=protected)
    def file_origins(sha256: str):
        return db.all('SELECT o.*,a.name account_name,a.provider FROM origins o JOIN accounts a ON a.id=o.account_id WHERE sha256=?', (sha256,))

    @app.get('/api/remotes', dependencies=protected)
    def list_remotes():
        try:
            return remotes(settings.root / 'config/rclone.conf')
        except ProviderError:
            raise HTTPException(400, 'Invalid rclone configuration') from None

    @app.post('/api/oauth/start', dependencies=protected)
    def oauth_start(body: dict):
        try:
            return oauth.start(str(body.get('provider', '')), str(body.get('name', '')))
        except OAuthError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.post('/api/oauth/{session}/continue', dependencies=protected)
    def oauth_continue(session: str, body: dict):
        try:
            return oauth.continue_(session, body.get('result', ''))
        except OAuthError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.get('/api/settings', dependencies=protected)
    def app_settings():
        return {'root': str(settings.root), 'source_root': str(settings.source_root),
                'version': app.version, 'authentication': 'rclone OAuth on server',
                'oauth_setup': 'docker compose exec cloud-sync rclone config --config /DATA/CloudSync/config/rclone.conf',
                'oauth_reconnect': 'docker compose exec cloud-sync rclone config reconnect REMOTE: --config /DATA/CloudSync/config/rclone.conf'}

    @app.get('/api/update', dependencies=protected)
    def update_status():
        return latest(app.version)

    if (settings.web_root / 'assets').exists():
        app.mount('/assets', StaticFiles(directory=settings.web_root / 'assets'), name='assets')

    @app.get('/')
    def index():
        if (settings.web_root / 'index.html').exists():
            return FileResponse(settings.web_root / 'index.html')
        return {'application': app.title, 'version': app.version}

    return app
