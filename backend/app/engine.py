import hashlib
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .db import now
from .providers import Cancelled, ProviderError, build_provider


class Engine:
    def __init__(self, db, settings, provider_factory=build_provider):
        self.db, self.settings, self.provider_factory = db, settings, provider_factory
        self.stop_event = threading.Event()
        # One writer avoids duplicate physical commits and limits NAS resource usage.
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='sync')
        self.scheduler = None

    def start(self):
        self.db.execute("UPDATE jobs SET status='failed', finished_at=?, current_file=NULL WHERE status IN ('started','running')", (now(),))
        self.scheduler = threading.Thread(target=self.schedule_loop, daemon=True)
        self.scheduler.start()

    def close(self):
        self.stop_event.set()
        if self.scheduler:
            self.scheduler.join(timeout=5)
        self.pool.shutdown(wait=True)

    def submit(self, account_id):
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            account = conn.execute('SELECT * FROM accounts WHERE id=? AND enabled=1', (account_id,)).fetchone()
            if not account:
                raise ValueError('Account is disabled or missing')
            active = conn.execute("SELECT id FROM jobs WHERE account_id=? AND status IN ('started','running')", (account_id,)).fetchone()
            if active:
                return active['id']
            job_id = conn.execute("INSERT INTO jobs(account_id,status,started_at) VALUES(?,'started',?)", (account_id, now())).lastrowid
            next_sync = (datetime.now(timezone.utc) + timedelta(minutes=account['interval_minutes'])).isoformat() if account['interval_minutes'] else None
            conn.execute('UPDATE accounts SET next_sync=? WHERE id=?', (next_sync, account_id))
        self.pool.submit(self.run, job_id)
        return job_id

    def schedule_loop(self):
        while not self.stop_event.is_set():
            try:
                for account in self.db.all('SELECT id FROM accounts WHERE enabled=1 AND interval_minutes>0 AND next_sync<=?', (now(),)):
                    self.submit(account['id'])
            except Exception:
                # Never log raw provider exceptions (may contain tokens).
                pass
            self.stop_event.wait(5)

    def cancelled(self, job_id):
        return self.stop_event.is_set() or bool(self.db.one('SELECT cancel_requested FROM jobs WHERE id=?', (job_id,))['cancel_requested'])

    def increment(self, job_id, column, amount=1):
        if column not in ('found', 'existing', 'new', 'duplicates', 'downloaded', 'errors', 'bytes_done'):
            raise ValueError('Invalid counter')
        self.db.execute(f'UPDATE jobs SET {column}={column}+? WHERE id=?', (amount, job_id))

    def run(self, job_id):
        job = self.db.one('SELECT * FROM jobs WHERE id=?', (job_id,))
        account = self.db.one('SELECT * FROM accounts WHERE id=?', (job['account_id'],))
        self.db.execute("UPDATE jobs SET status='running' WHERE id=?", (job_id,))
        self.db.event(job_id, 'info', 'Synchronization started')
        state = 'completed'
        try:
            if self.cancelled(job_id):
                raise Cancelled()
            provider = self.provider_factory(account, self.settings)
            cancel = lambda: self.cancelled(job_id)
            # Discovery is complete before progress starts, giving a stable denominator.
            entries = list(provider.discover(cancel))
            self.increment(job_id, 'found', len(entries))
            for entry in entries:
                if cancel():
                    raise Cancelled()
                self.db.execute('UPDATE jobs SET current_file=? WHERE id=?', (entry.path, job_id))
                origin = self.db.one('SELECT o.*, b.local_path FROM origins o JOIN blobs b USING(sha256) WHERE account_id=? AND remote_id=?', (account['id'], entry.remote_id))
                if origin and origin['fingerprint'] == entry.fingerprint:
                    path = self.settings.root / origin['local_path']
                    if path.is_file() and path.stat().st_size == origin['size']:
                        self.increment(job_id, 'existing')
                        continue
                self.increment(job_id, 'new')
                for attempt in range(3):
                    try:
                        self.download(job_id, account, entry, provider, cancel)
                        break
                    except Cancelled:
                        raise
                    except (OSError, ProviderError, EOFError, ValueError):
                        if attempt == 2:
                            self.increment(job_id, 'errors')
                            self.db.event(job_id, 'error', 'File transfer failed after 3 attempts; partial download retained')
                        else:
                            self.db.event(job_id, 'warning', 'Temporary transfer failure; retrying')
                            if self.stop_event.wait(2 ** attempt):
                                raise Cancelled()
            if self.db.one('SELECT errors FROM jobs WHERE id=?', (job_id,))['errors']:
                state = 'failed'
        except Cancelled:
            state = 'cancelled'
        except Exception:
            state = 'failed'
            self.increment(job_id, 'errors')
            self.db.event(job_id, 'error', 'Synchronization failed; check source availability and authorization')
        finally:
            self.db.execute('UPDATE jobs SET status=?,finished_at=?,current_file=NULL WHERE id=?', (state, now(), job_id))
            self.db.event(job_id, 'info', f'Synchronization {state}')

    def download(self, job_id, account, entry, provider, cancel):
        key = hashlib.sha256(f'{account["id"]}:{entry.remote_id}'.encode()).hexdigest()
        part = self.settings.root / 'data/.parts' / f'{key}.part'
        digest = hashlib.sha256()
        size = 0
        with part.open('wb') as output:
            for chunk in provider.chunks(entry, cancel):
                if cancel():
                    raise Cancelled()
                output.write(chunk)
                digest.update(chunk)
                size += len(chunk)
            output.flush()
            os.fsync(output.fileno())
        if entry.size >= 0 and size != entry.size:
            raise ProviderError('Incomplete download')
        sha = digest.hexdigest()
        existing = self.db.one('SELECT * FROM blobs WHERE sha256=?', (sha,))
        suffix = Path(entry.path).suffix.lower()
        if not re.fullmatch(r'\.[a-z0-9]{1,12}', suffix):
            suffix = ''
        relative = existing['local_path'] if existing else f'data/{sha[:2]}/{sha}{suffix}'
        destination = self.settings.root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        duplicate = destination.exists()
        if duplicate:
            # Verify any existing/orphan blob before trusting it; never overwrite corruption.
            verify = hashlib.sha256()
            with destination.open('rb') as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    verify.update(chunk)
            if verify.hexdigest() != sha:
                raise ProviderError('Local integrity mismatch; operator intervention required')
            part.unlink()
        else:
            # Same filesystem; publish atomically without overwriting an existing file.
            os.link(part, destination)
            part.unlink()
            directory_fd = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        with self.db.connect() as conn:
            conn.execute('INSERT OR IGNORE INTO blobs VALUES(?,?,?,?,?)', (sha, size, relative, entry.mime, now()))
            conn.execute('''INSERT INTO origins(account_id,remote_id,original_path,name,size,mime,fingerprint,sha256,synced_at)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(account_id,remote_id) DO UPDATE SET
                original_path=excluded.original_path,name=excluded.name,size=excluded.size,mime=excluded.mime,
                fingerprint=excluded.fingerprint,sha256=excluded.sha256,synced_at=excluded.synced_at,status='stored' ''',
                         (account['id'], entry.remote_id, entry.path, Path(entry.path).name, size, entry.mime, entry.fingerprint, sha, now()))
        self.increment(job_id, 'downloaded')
        self.increment(job_id, 'bytes_done', size)
        if duplicate:
            self.increment(job_id, 'duplicates')
