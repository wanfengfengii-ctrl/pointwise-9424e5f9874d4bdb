from dataclasses import dataclass
from sqlite3 import Connection

from archive.manifest import Manifest
from archive.manifest_store import load_manifest
from archive.receipts import IssueReceipt, load_receipt
from handoff.catalog import lookup_issue


MANIFEST_NOT_FOUND = None


class HandoffIntegrityError(RuntimeError):
    """A published handoff entry does not match the archived delivery."""


@dataclass(frozen=True, slots=True)
class ManifestDelivery:
    manifest: Manifest
    receipt: IssueReceipt


def get_manifest(db: Connection, manifest_id: int) -> ManifestDelivery | None:
    entry = lookup_issue(db, manifest_id)
    if entry is None:
        return MANIFEST_NOT_FOUND
    manifest = load_manifest(db, entry.manifest_id)
    receipt = load_receipt(db, entry.manifest_id)
    if (manifest is None or receipt is None
            or receipt.evidence_id != entry.evidence_id
            or manifest.evidence_id != entry.evidence_id
            or manifest.line_id != entry.line_id or manifest.run_id != entry.run_id):
        raise HandoffIntegrityError(f'incomplete or inconsistent delivery for manifest {manifest_id}')
    return ManifestDelivery(manifest, receipt)
