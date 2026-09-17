import hashlib
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database, now
from app.engine import Engine
from app.main import create_app
from app.providers import Entry, FilesystemProvider, ProviderError, RcloneProvider


@pytest.fixture
def setup(tmp_path):
    settings = Settings(tmp_path / 'store', tmp_path / 'sources', 'x' * 32)
    settings.source_root.mkdir()
    settings.prepare()
    db = Database(settings.root / 'database/cloudsync.sqlite3')
    db.migrate()
    return settings, db


def account(db, location='.', provider='filesystem'):
    return db.execute('INSERT INTO accounts(name,provider,location,interval_minutes,created_at) VALUES(?,?,?,0,?)', ('Test', provider, location, now()))


def run(settings, db, account_id, factory=None):
    engine = Engine(db, settings, **({'provider_factory': factory} if factory else {}))
    job = db.execute("INSERT INTO jobs(account_id,status,started_at) VALUES(?,'started',?)", (account_id, now()))
    engine.run(job)
    engine.close()
    return db.one('SELECT * FROM jobs WHERE id=?', (job,))


def physical(settings):
    return [p for p in (settings.root / 'data').rglob('*') if p.is_file() and p.suffix != '.part']


def test_same_sha_one_copy_and_two_origins(setup):
    settings, db = setup
    (settings.source_root / 'photo.jpg').write_bytes(b'same content')
    first, second = account(db), account(db)
    assert run(settings, db, first)['downloaded'] == 1
    assert run(settings, db, second)['duplicates'] == 1
    assert len(physical(settings)) == 1
    assert len(db.all('SELECT * FROM origins')) == 2


def test_distinct_hashes_incremental_and_changed_source(setup):
    settings, db = setup
    source = settings.source_root / 'photo.jpg'
    source.write_bytes(b'original')
    aid = account(db)
    run(settings, db, aid)
    assert run(settings, db, aid)['existing'] == 1
    source.write_bytes(b'changed content')
    assert run(settings, db, aid)['downloaded'] == 1
    assert len(physical(settings)) == 2
    source.unlink()
    assert run(settings, db, aid)['status'] == 'completed'
    assert len(physical(settings)) == 2


def test_incomplete_keeps_part_and_never_indexes(setup, monkeypatch):
    settings, db = setup
    class Broken:
        def discover(self, cancel):
            yield Entry('1', 'file.jpg', 100, 'image/jpeg', '1')
        def chunks(self, entry, cancel):
            yield b'partial'
    monkeypatch.setattr('threading.Event.wait', lambda *args: False)
    job = run(settings, db, account(db), lambda *args: Broken())
    assert job['status'] == 'failed'
    assert list((settings.root / 'data/.parts').glob('*.part'))[0].read_bytes() == b'partial'
    assert not db.all('SELECT * FROM blobs')
    assert not physical(settings)


def test_provider_failure_preserves_existing(setup):
    settings, db = setup
    (settings.source_root / 'file').write_bytes(b'keep')
    aid = account(db)
    run(settings, db, aid)
    class Broken:
        def discover(self, cancel):
            raise ProviderError('secret-token-must-not-be-logged')
    assert run(settings, db, aid, lambda *args: Broken())['status'] == 'failed'
    assert physical(settings)[0].read_bytes() == b'keep'
    assert 'secret-token' not in str(db.all('SELECT * FROM events'))


def test_restart_and_migration_preserve_data(setup):
    settings, db = setup
    (settings.source_root / 'file').write_bytes(b'persist')
    aid = account(db)
    run(settings, db, aid)
    # Reopen the same external state, exactly as a recreated container does.
    newer = Database(db.path)
    newer.migrate()
    engine = Engine(newer, settings)
    engine.start()
    engine.close()
    assert len(newer.all('SELECT * FROM blobs')) == 1
    assert physical(settings)[0].read_bytes() == b'persist'
    assert run(settings, newer, aid)['existing'] == 1


def test_remote_command_surface_never_mutates(setup):
    settings, _ = setup
    config = settings.root / 'config/rclone.conf'
    config.write_text('[personal]\ntype = drive\n')
    provider = RcloneProvider('personal:', 'google_drive', config)
    for op in ('delete', 'purge', 'move', 'sync', 'copy', 'copyto', 'rmdir'):
        with pytest.raises(ProviderError):
            provider.command(op, 'personal:')
    assert provider.command('cat', 'personal:file')[1:3] == ['cat', 'personal:file']
    assert not hasattr(provider, 'delete')


def test_takeout_archives_never_extract_paths(setup):
    settings, db = setup
    with zipfile.ZipFile(settings.source_root / 'takeout.zip', 'w') as archive:
        archive.writestr('../../escape.jpg', b'picture')
        archive.writestr('Photos/duplicate.jpg', b'picture')
    result = run(settings, db, account(db, '.', 'takeout'))
    assert result['status'] == 'completed'
    assert result['duplicates'] == 1
    assert len(physical(settings)) == 1
    assert not (settings.root.parent / 'escape.jpg').exists()


def test_path_traversal_and_symlink_rejected(setup):
    settings, _ = setup
    with pytest.raises(ProviderError):
        FilesystemProvider('../store', settings.source_root)
    (settings.source_root / 'secret').symlink_to(settings.root / 'database/cloudsync.sqlite3')
    assert list(FilesystemProvider('.', settings.source_root).discover(lambda: False)) == []


def test_api_auth_accounts_search_and_disable(setup):
    settings, _ = setup
    (settings.source_root / 'hello.txt').write_text('hello')
    with TestClient(create_app(settings, background=False)) as client:
        assert client.get('/health').status_code == 200
        assert client.get('/api/dashboard').status_code == 401
        client.headers['Authorization'] = 'Bearer ' + settings.token
        added = client.post('/api/accounts', json={'name': 'Disk', 'provider': 'filesystem', 'location': '.', 'interval_minutes': 0})
        assert added.status_code == 201
        aid = added.json()['id']
        db = client.app.state.db
        run(settings, db, aid)
        result = client.get('/api/files', params={'extension': 'txt'}).json()
        assert result['total'] == 1
        assert result['items'][0]['sha256'] == hashlib.sha256(b'hello').hexdigest()
        assert client.delete(f'/api/accounts/{aid}').status_code == 200
        assert client.post(f'/api/accounts/{aid}/sync').status_code == 409
        assert len(physical(settings)) == 1


def test_duplicate_submit_returns_same_job(setup, monkeypatch):
    settings, db = setup
    engine = Engine(db, settings)
    monkeypatch.setattr(engine.pool, 'submit', lambda *args: None)
    aid = account(db)
    assert engine.submit(aid) == engine.submit(aid)
    engine.close()


def test_cancellation_keeps_part(setup):
    settings, db = setup
    class Slow:
        def discover(self, cancel):
            yield Entry('1', 'big.bin', 20, 'application/octet-stream', '1')
        def chunks(self, entry, cancel):
            yield b'first'
            db.execute('UPDATE jobs SET cancel_requested=1')
            yield b'second'
    result = run(settings, db, account(db), lambda *args: Slow())
    assert result['status'] == 'cancelled'
    assert not physical(settings)
    assert list((settings.root / 'data/.parts').glob('*.part'))


def test_orphan_after_crash_reused_with_different_extension(setup):
    settings, db = setup
    content = b'orphaned after atomic publication'
    sha = hashlib.sha256(content).hexdigest()
    orphan = settings.root / 'data' / sha[:2] / (sha + '.jpg')
    orphan.parent.mkdir()
    orphan.write_bytes(content)
    (settings.source_root / 'renamed.png').write_bytes(content)
    assert run(settings, db, account(db))['duplicates'] == 1
    assert len(physical(settings)) == 1
    assert db.one('SELECT local_path FROM blobs')['local_path'].endswith('.jpg')


def test_second_worker_rejected(setup):
    settings, db = setup
    first, second = Engine(db, settings), Engine(db, settings)
    first.start()
    try:
        with pytest.raises(RuntimeError, match='Another sync worker'):
            second.start()
    finally:
        first.close()
        second.close()


def test_scheduler_enqueues_due_account_and_advances_schedule(setup, monkeypatch):
    settings, db = setup
    aid = account(db)
    db.execute("UPDATE accounts SET interval_minutes=60,next_sync='2000-01-01T00:00:00+00:00' WHERE id=?", (aid,))
    engine = Engine(db, settings)
    monkeypatch.setattr(engine.pool, 'submit', lambda *args: None)
    monkeypatch.setattr(engine.stop_event, 'wait', lambda *args: engine.stop_event.set())
    engine.schedule_loop()
    assert len(db.all('SELECT * FROM jobs')) == 1
    assert db.one('SELECT next_sync FROM accounts')['next_sync'] > now()
    engine.close()


def test_interrupted_job_marked_failed_after_restart(setup):
    settings, db = setup
    aid = account(db)
    db.execute("INSERT INTO jobs(account_id,status,started_at) VALUES(?,'running',?)", (aid, now()))
    engine = Engine(db, settings)
    engine.start()
    engine.close()
    assert db.one('SELECT status FROM jobs')['status'] == 'failed'


def test_corrupt_existing_content_is_not_overwritten(setup, monkeypatch):
    settings, db = setup
    content = b'correct'
    (settings.source_root / 'file.jpg').write_bytes(content)
    sha = hashlib.sha256(content).hexdigest()
    corrupt = settings.root / 'data' / sha[:2] / (sha + '.jpg')
    corrupt.parent.mkdir()
    corrupt.write_bytes(b'damaged')
    monkeypatch.setattr('threading.Event.wait', lambda *args: False)
    assert run(settings, db, account(db))['status'] == 'failed'
    assert corrupt.read_bytes() == b'damaged'
    assert not db.all('SELECT * FROM blobs')
