import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from archive.manifest_store import install_manifest_schema
from archive.receipts import install_receipt_schema
from capture.packs import install_pack_schema
from handoff.catalog import install_catalog_schema
from runs.lifecycle import RunError, RunRecord, RunStage
from runs.lines import install_line_schema, seed_lines
from source.opening import RecordingOrigin


SCHEMA_VERSION = 1


def open_store(path: str | Path) -> sqlite3.Connection:
    db = sqlite3.connect(path, isolation_level=None)
    try:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys = ON')
    except sqlite3.Error:
        db.close()
        raise
    return db


@contextmanager
def write_transaction(db: sqlite3.Connection) -> Iterator[None]:
    db.execute('BEGIN IMMEDIATE')
    try:
        yield
        db.commit()
    except BaseException:
        db.rollback()
        raise


def initialize_store(db: sqlite3.Connection) -> None:
    with write_transaction(db):
        db.execute('''
            CREATE TABLE IF NOT EXISTS station_init (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                version INTEGER NOT NULL
            )
        ''')
        existing = db.execute('SELECT version FROM station_init WHERE singleton = 1').fetchone()
        if existing is not None:
            if existing['version'] != SCHEMA_VERSION:
                raise RunError(f'unsupported station schema version {existing["version"]}')
            return

        install_line_schema(db)
        install_run_schema(db)
        install_pack_schema(db)
        install_manifest_schema(db)
        install_receipt_schema(db)
        install_catalog_schema(db)
        seed_lines(db)
        db.execute('INSERT INTO station_init (singleton, version) VALUES (1, ?)', (SCHEMA_VERSION,))


def install_run_schema(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE runs (
            line_id TEXT NOT NULL REFERENCES lines(line_id),
            run_id TEXT NOT NULL,
            origin_path TEXT NOT NULL,
            origin_digest TEXT NOT NULL,
            stage TEXT NOT NULL,
            evidence_id INTEGER UNIQUE REFERENCES evidence_packs(evidence_id),
            failure TEXT,
            PRIMARY KEY (line_id, run_id),
            CHECK (
                (stage IN ('registered', 'recording') AND evidence_id IS NULL AND failure IS NULL)
                OR (stage = 'recorded' AND evidence_id IS NOT NULL AND failure IS NULL)
                OR (stage = 'failed' AND evidence_id IS NULL AND failure IS NOT NULL)
            )
        )
    ''')


def load_run_record(db: sqlite3.Connection, line_id: str, run_id: str) -> RunRecord | None:
    row = db.execute('''
        SELECT line_id, run_id, origin_path, origin_digest, stage, evidence_id, failure
        FROM runs WHERE line_id = ? AND run_id = ?
    ''', (line_id, run_id)).fetchone()
    if row is None:
        return None
    return RunRecord(
        line_id=row['line_id'],
        run_id=row['run_id'],
        origin=RecordingOrigin(row['origin_path'], row['origin_digest']),
        stage=RunStage(row['stage']),
        evidence_id=row['evidence_id'],
        failure=row['failure'],
    )


def insert_run_record(db: sqlite3.Connection, record: RunRecord) -> None:
    db.execute('''
        INSERT INTO runs (line_id, run_id, origin_path, origin_digest, stage)
        VALUES (?, ?, ?, ?, ?)
    ''', (record.line_id, record.run_id, record.origin.path, record.origin.sha256, record.stage))


def save_run_stage(db: sqlite3.Connection, record: RunRecord, expected: RunStage) -> None:
    result = db.execute('''
        UPDATE runs SET stage = ?, evidence_id = ?, failure = ?
        WHERE line_id = ? AND run_id = ? AND stage = ?
    ''', (record.stage, record.evidence_id, record.failure, record.line_id, record.run_id, expected))
    if result.rowcount != 1:
        raise RunError(f'run {record.line_id}/{record.run_id} no longer has stage {expected}')
