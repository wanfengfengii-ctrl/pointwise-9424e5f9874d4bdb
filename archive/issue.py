import sqlite3

from archive.locate import assess_trajectory
from archive.manifest import build_manifest
from archive.manifest_store import find_manifest_by_evidence, store_manifest
from archive.receipts import IssueReceipt, store_receipt
from capture.packs import EvidencePack, EvidenceSlot, load_pack
from handoff.catalog import HandoffEntry, index_issue
from handoff.lookup import ManifestDelivery, get_manifest
from runs.store import write_transaction
from source.events import TURN_LENGTH
from source.opening import RecordingOrigin


class InvalidEvidence(ValueError):
    """The request does not identify a valid frozen payload."""


class IssueWriteError(RuntimeError):
    """A complete issuance could not be committed."""


def validate_issue_evidence(pack: EvidencePack) -> None:
    if not isinstance(pack, EvidencePack):
        raise InvalidEvidence('expected a frozen evidence pack')
    if type(pack.evidence_id) is not int or not 0 < pack.evidence_id < 2**63:
        raise InvalidEvidence('expected a fixed evidence number')
    origin = pack.origin
    if (not isinstance(origin, RecordingOrigin) or type(origin.path) is not str
            or not origin.path or type(origin.sha256) is not str or len(origin.sha256) != 64
            or any(character not in '0123456789abcdef' for character in origin.sha256)):
        raise InvalidEvidence('invalid recording origin')
    if (type(pack.line_id) is not str or not pack.line_id.strip()
            or type(pack.run_id) is not str or not pack.run_id.strip()):
        raise InvalidEvidence('invalid inspection identity')
    if type(pack.slots) is not tuple or not pack.slots:
        raise InvalidEvidence('evidence requires a nonempty ordered slot tuple')

    events = set()
    last_reading = 0
    for expected, slot in enumerate(pack.slots):
        if (not isinstance(slot, EvidenceSlot) or type(slot.slot) is not int or slot.slot != expected
                or type(slot.tick) is not int or not 0 <= slot.tick < TURN_LENGTH
                or type(slot.value) is not int):
            raise InvalidEvidence(f'invalid reading at physical slot {expected}')
        if (type(slot.reading_event) is not int or slot.reading_event <= last_reading
                or slot.reading_event in events):
            raise InvalidEvidence(f'invalid reading event at slot {expected}')
        events.add(slot.reading_event)
        last_reading = slot.reading_event

        if slot.mark is None:
            if slot.mark_event is not None:
                raise InvalidEvidence(f'mark event without mark at slot {expected}')
        else:
            if (type(slot.mark) is not int or type(slot.mark_event) is not int
                    or slot.mark_event <= 0 or slot.mark_event in events):
                raise InvalidEvidence(f'invalid mark at slot {expected}')
            events.add(slot.mark_event)

    if pack.slots[0].mark is None:
        raise InvalidEvidence('evidence requires a first-slot absolute mark')


def issue_manifest(
    db: sqlite3.Connection, pack: EvidencePack, *, fail_before_commit: bool = False
) -> ManifestDelivery:
    validate_issue_evidence(pack)
    evidence_id = pack.evidence_id
    try:
        with write_transaction(db):
            if load_pack(db, evidence_id) != pack:
                raise InvalidEvidence('payload differs from the specified frozen evidence')
            existing_id = find_manifest_by_evidence(db, evidence_id)
            if existing_id is not None:
                existing = get_manifest(db, existing_id)
                if existing is None:
                    raise IssueWriteError('existing manifest has no published handoff entry')
                return existing

            assessment = assess_trajectory(pack)
            manifest = store_manifest(db, build_manifest(pack, assessment))
            manifest_id = manifest.manifest_id
            if manifest_id is None:
                raise IssueWriteError('manifest insert did not allocate an identifier')
            receipt = IssueReceipt(manifest_id, evidence_id)
            store_receipt(db, receipt)
            index_issue(db, HandoffEntry(manifest_id, evidence_id, pack.line_id, pack.run_id))
            if fail_before_commit:
                raise sqlite3.OperationalError('injected failure before issue commit')
            return ManifestDelivery(manifest, receipt)
    except sqlite3.Error as error:
        raise IssueWriteError(f'could not issue evidence {evidence_id}: {error}') from error
