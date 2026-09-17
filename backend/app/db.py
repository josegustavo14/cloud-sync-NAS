import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


# Append migrations; never replace an already released migration.
MIGRATIONS = ["""
CREATE TABLE accounts (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, provider TEXT NOT NULL,
 location TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
 interval_minutes INTEGER NOT NULL DEFAULT 360, next_sync TEXT,
 created_at TEXT NOT NULL
);
CREATE TABLE blobs (
 sha256 TEXT PRIMARY KEY, size INTEGER NOT NULL,
 local_path TEXT NOT NULL UNIQUE, mime TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE origins (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id),
 remote_id TEXT NOT NULL, original_path TEXT NOT NULL, name TEXT NOT NULL,
 size INTEGER NOT NULL, mime TEXT NOT NULL, fingerprint TEXT NOT NULL,
 sha256 TEXT NOT NULL REFERENCES blobs(sha256), synced_at TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'stored', UNIQUE(account_id, remote_id)
);
CREATE TABLE jobs (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id),
 status TEXT NOT NULL CHECK(status IN ('started','running','completed','failed','cancelled')),
 started_at TEXT NOT NULL, finished_at TEXT, found INTEGER NOT NULL DEFAULT 0,
 existing INTEGER NOT NULL DEFAULT 0, new INTEGER NOT NULL DEFAULT 0,
 duplicates INTEGER NOT NULL DEFAULT 0, downloaded INTEGER NOT NULL DEFAULT 0,
 errors INTEGER NOT NULL DEFAULT 0, bytes_done INTEGER NOT NULL DEFAULT 0,
 current_file TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX one_active_job ON jobs(account_id) WHERE status IN ('started','running');
CREATE TABLE events (
 id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES jobs(id),
 created_at TEXT NOT NULL, level TEXT NOT NULL, message TEXT NOT NULL
);
CREATE INDEX origins_hash ON origins(sha256);
CREATE INDEX jobs_recent ON jobs(started_at DESC);
CREATE INDEX events_job ON events(job_id, id);
"""]


class Database:
    def __init__(self, path):
        self.path = path

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def migrate(self):
        with self.connect() as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            version = conn.execute('PRAGMA user_version').fetchone()[0]
            if version > len(MIGRATIONS):
                raise RuntimeError('Database is newer than this application; downgrade refused')
            for i in range(version, len(MIGRATIONS)):
                conn.executescript('BEGIN IMMEDIATE;\n' + MIGRATIONS[i] +
                                   f'\nPRAGMA user_version={i + 1};\nCOMMIT;')

    def all(self, sql, params=()):
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, params)]

    def one(self, sql, params=()):
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def execute(self, sql, params=()):
        with self.connect() as conn:
            return conn.execute(sql, params).lastrowid

    def event(self, job_id, level, message):
        self.execute('INSERT INTO events(job_id,created_at,level,message) VALUES(?,?,?,?)',
                     (job_id, now(), level, message))
