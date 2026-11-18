from dataclasses import dataclass
from sqlite3 import Connection


@dataclass(frozen=True, slots=True)
class HandoffEntry:
    manifest_id: int
    evidence_id: int
    line_id: str
    run_id: str


def install_catalog_schema(db: Connection) -> None:
    db.execute('''
        CREATE TABLE handoff_entries (
            manifest_id INTEGER PRIMARY KEY REFERENCES issue_receipts(manifest_id),
            evidence_id INTEGER NOT NULL UNIQUE REFERENCES evidence_packs(evidence_id),
            line_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            FOREIGN KEY (line_id, run_id) REFERENCES runs(line_id, run_id)
        )
    ''')


def index_issue(db: Connection, entry: HandoffEntry) -> None:
    db.execute('''
        INSERT INTO handoff_entries (manifest_id, evidence_id, line_id, run_id)
        VALUES (?, ?, ?, ?)
    ''', (entry.manifest_id, entry.evidence_id, entry.line_id, entry.run_id))


def lookup_issue(db: Connection, manifest_id: int) -> HandoffEntry | None:
    if type(manifest_id) is not int or not 0 < manifest_id < 2**63:
        return None
    row = db.execute('''
        SELECT manifest_id, evidence_id, line_id, run_id FROM handoff_entries WHERE manifest_id = ?
    ''', (manifest_id,)).fetchone()
    if row is None:
        return None
    return HandoffEntry(row['manifest_id'], row['evidence_id'], row['line_id'], row['run_id'])
