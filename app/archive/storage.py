from contextlib import contextmanager
from pathlib import Path
import sqlite3


class TrackArchive:
    def __init__(self, filename):
        self.file = Path(filename)
        self.file.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, payload BLOB NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS issues (run_id TEXT PRIMARY KEY REFERENCES runs(id), seal TEXT NOT NULL)')

    @contextmanager
    def transaction(self, write=True):
        """一次事务一个连接；写事务先取锁，读事务不挡住同时归档的批次。"""
        db = sqlite3.connect(self.file, timeout=30, isolation_level=None)
        try:
            db.execute('PRAGMA busy_timeout=30000')
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            try:
                yield db
            except BaseException:
                try:
                    db.execute('ROLLBACK')
                except sqlite3.Error:
                    pass
                raise
            else:
                db.execute('COMMIT')
        finally:
            db.close()
