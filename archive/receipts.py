from dataclasses import dataclass
from sqlite3 import Connection


@dataclass(frozen=True, slots=True)
class IssueReceipt:
    manifest_id: int
    evidence_id: int


def install_receipt_schema(db: Connection) -> None:
    db.execute('''
        CREATE TABLE issue_receipts (
            manifest_id INTEGER PRIMARY KEY REFERENCES manifests(manifest_id),
            evidence_id INTEGER NOT NULL UNIQUE REFERENCES evidence_packs(evidence_id)
        )
    ''')


def store_receipt(db: Connection, receipt: IssueReceipt) -> None:
    db.execute('INSERT INTO issue_receipts (manifest_id, evidence_id) VALUES (?, ?)',
               (receipt.manifest_id, receipt.evidence_id))


def load_receipt(db: Connection, manifest_id: int) -> IssueReceipt | None:
    row = db.execute('SELECT manifest_id, evidence_id FROM issue_receipts WHERE manifest_id = ?',
                     (manifest_id,)).fetchone()
    if row is None:
        return None
    return IssueReceipt(row['manifest_id'], row['evidence_id'])
