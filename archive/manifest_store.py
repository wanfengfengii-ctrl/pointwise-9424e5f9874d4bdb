from dataclasses import replace
from sqlite3 import Connection

from archive.manifest import Manifest, ManifestRow
from source.format import integer_text, parse_integer
from source.opening import RecordingOrigin


def install_manifest_schema(db: Connection) -> None:
    db.execute('''
        CREATE TABLE manifests (
            manifest_id INTEGER PRIMARY KEY,
            evidence_id INTEGER NOT NULL UNIQUE REFERENCES evidence_packs(evidence_id),
            line_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            origin_path TEXT NOT NULL,
            origin_digest TEXT NOT NULL,
            FOREIGN KEY (line_id, run_id) REFERENCES runs(line_id, run_id)
        )
    ''')
    db.execute('''
        CREATE TABLE manifest_rows (
            manifest_id INTEGER NOT NULL REFERENCES manifests(manifest_id),
            slot INTEGER NOT NULL,
            tick INTEGER NOT NULL,
            reading_value TEXT NOT NULL,
            position TEXT,
            PRIMARY KEY (manifest_id, slot)
        )
    ''')


def store_manifest(db: Connection, manifest: Manifest) -> Manifest:
    if manifest.manifest_id is not None:
        raise ValueError('a numbered manifest cannot be inserted again')
    result = db.execute('''
        INSERT INTO manifests (evidence_id, line_id, run_id, origin_path, origin_digest)
        VALUES (?, ?, ?, ?, ?)
    ''', (manifest.evidence_id, manifest.line_id, manifest.run_id,
          manifest.origin.path, manifest.origin.sha256))
    manifest_id = result.lastrowid
    db.executemany('''
        INSERT INTO manifest_rows (manifest_id, slot, tick, reading_value, position)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        (manifest_id, row.slot, row.tick, integer_text(row.value),
         integer_text(row.position) if row.position is not None else None)
        for row in manifest.rows
    ))
    return replace(manifest, manifest_id=manifest_id)


def load_manifest(db: Connection, manifest_id: int) -> Manifest | None:
    header = db.execute('''
        SELECT manifest_id, evidence_id, line_id, run_id, origin_path, origin_digest
        FROM manifests WHERE manifest_id = ?
    ''', (manifest_id,)).fetchone()
    if header is None:
        return None
    records = db.execute('''
        SELECT slot, tick, reading_value, position FROM manifest_rows
        WHERE manifest_id = ? ORDER BY slot
    ''', (manifest_id,))
    rows = tuple(
        ManifestRow(
            slot=row['slot'],
            tick=row['tick'],
            value=parse_integer(row['reading_value']),
            position=parse_integer(row['position']) if row['position'] is not None else None,
        )
        for row in records
    )
    return Manifest(
        manifest_id=header['manifest_id'],
        evidence_id=header['evidence_id'],
        line_id=header['line_id'],
        run_id=header['run_id'],
        origin=RecordingOrigin(header['origin_path'], header['origin_digest']),
        rows=rows,
    )


def find_manifest_by_evidence(db: Connection, evidence_id: int) -> int | None:
    row = db.execute(
        'SELECT manifest_id FROM manifests WHERE evidence_id = ?', (evidence_id,)
    ).fetchone()
    return row['manifest_id'] if row is not None else None
