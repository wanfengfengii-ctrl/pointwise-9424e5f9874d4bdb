from sqlite3 import Connection

from capture.packs import EvidencePack, load_pack


EVIDENCE_NOT_FOUND = None


def get_evidence(db: Connection, evidence_id: int) -> EvidencePack | None:
    pack = load_pack(db, evidence_id)
    if pack is None:
        return EVIDENCE_NOT_FOUND
    return pack
