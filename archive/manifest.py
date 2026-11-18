from dataclasses import dataclass

from archive.locate import LocationAssessment
from capture.packs import EvidencePack
from source.opening import RecordingOrigin


@dataclass(frozen=True, slots=True)
class ManifestRow:
    slot: int
    tick: int
    value: int
    position: int | None


@dataclass(frozen=True, slots=True)
class Manifest:
    manifest_id: int | None
    evidence_id: int
    line_id: str
    run_id: str
    origin: RecordingOrigin
    rows: tuple[ManifestRow, ...]


def build_manifest(pack: EvidencePack, assessment: LocationAssessment) -> Manifest:
    if pack.evidence_id is None:
        raise ValueError('a manifest requires numbered evidence')
    rows = tuple(
        ManifestRow(slot.slot, slot.tick, slot.value, position)
        for slot, position in zip(pack.slots, assessment.positions, strict=True)
    )
    return Manifest(None, pack.evidence_id, pack.line_id, pack.run_id, pack.origin, rows)
