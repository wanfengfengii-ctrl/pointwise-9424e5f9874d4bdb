import json
from dataclasses import asdict, dataclass, replace
from sqlite3 import Connection

from source.format import encode_json, parse_integer
from source.opening import RecordingOrigin


@dataclass(frozen=True, slots=True)
class EvidenceSlot:
    slot: int
    tick: int
    value: int
    reading_event: int
    mark: int | None = None
    mark_event: int | None = None


@dataclass(frozen=True, slots=True)
class EvidencePack:
    evidence_id: int | None
    line_id: str
    run_id: str
    origin: RecordingOrigin
    slots: tuple[EvidenceSlot, ...]


def install_pack_schema(db: Connection) -> None:
    db.execute('''
        CREATE TABLE evidence_packs (
            evidence_id INTEGER PRIMARY KEY,
            line_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            origin_path TEXT NOT NULL,
            origin_digest TEXT NOT NULL,
            slots_json TEXT NOT NULL,
            UNIQUE (line_id, run_id),
            FOREIGN KEY (line_id, run_id) REFERENCES runs(line_id, run_id)
        )
    ''')


def persist_pack(db: Connection, pack: EvidencePack) -> EvidencePack:
    if pack.evidence_id is not None:
        raise ValueError('a numbered evidence pack cannot be inserted again')
    slots_json = encode_json([asdict(slot) for slot in pack.slots])
    result = db.execute('''
        INSERT INTO evidence_packs (line_id, run_id, origin_path, origin_digest, slots_json)
        VALUES (?, ?, ?, ?, ?)
    ''', (pack.line_id, pack.run_id, pack.origin.path, pack.origin.sha256, slots_json))
    return replace(pack, evidence_id=result.lastrowid)


def load_pack(db: Connection, evidence_id: int) -> EvidencePack | None:
    if type(evidence_id) is not int or not 0 < evidence_id < 2**63:
        return None
    row = db.execute('''
        SELECT evidence_id, line_id, run_id, origin_path, origin_digest, slots_json
        FROM evidence_packs WHERE evidence_id = ?
    ''', (evidence_id,)).fetchone()
    if row is None:
        return None
    slots = json.loads(row['slots_json'], parse_int=parse_integer)
    return EvidencePack(
        evidence_id=row['evidence_id'],
        line_id=row['line_id'],
        run_id=row['run_id'],
        origin=RecordingOrigin(row['origin_path'], row['origin_digest']),
        slots=tuple(EvidenceSlot(**slot) for slot in slots),
    )
