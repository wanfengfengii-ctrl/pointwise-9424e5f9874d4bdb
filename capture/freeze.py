from sqlite3 import Connection

from capture.packs import EvidencePack, EvidenceSlot, persist_pack
from capture.session import CaptureSession
from capture.slots import CaptureError
from runs.lifecycle import RunError, RunRecord, RunStage
from runs.store import load_run_record, save_run_stage, write_transaction
from source.opening import RecordingError, open_recording
from source.replay import replay_events


def build_evidence_pack(record: RunRecord, session: CaptureSession) -> EvidencePack:
    session.check_ready()
    readings = session.slots.readings()
    latest_slot_by_tick = {reading.tick: reading.slot for reading in readings}
    slots = []
    for reading in readings:
        mark = session.marks.for_slot(reading.slot)
        if mark is None and latest_slot_by_tick[reading.tick] != reading.slot:
            continue
        slots.append(EvidenceSlot(
            slot=reading.slot,
            tick=reading.tick,
            value=reading.value,
            reading_event=reading.event_number,
            mark=mark.position if mark is not None else None,
            mark_event=mark.event_number if mark is not None else None,
        ))
    return EvidencePack(None, record.line_id, record.run_id, record.origin, tuple(slots))


def capture_run(db: Connection, line_id: str, run_id: str) -> int:
    with write_transaction(db):
        record = load_run_record(db, line_id, run_id)
        if record is None:
            raise RunError(f'unknown run {line_id}/{run_id}')
        recording = record.begin_recording()
        opened = open_recording(record.origin.path)
        if opened.origin != record.origin:
            raise RunError(f'recording source changed for {line_id}/{run_id}')
        save_run_stage(db, recording, RunStage.REGISTERED)

        try:
            replay = replay_events(opened)
            session = CaptureSession()
            for event in replay.events:
                session.accept(event)
            prepared = build_evidence_pack(recording, session)
        except (RecordingError, CaptureError) as error:
            failed = recording.fail_recording(str(error))
            save_run_stage(db, failed, RunStage.RECORDING)
            capture_failure = error
        else:
            pack = persist_pack(db, prepared)
            evidence_id = pack.evidence_id
            if evidence_id is None:
                raise RuntimeError('evidence insert did not allocate an identifier')
            save_run_stage(db, recording.finish_recording(evidence_id), RunStage.RECORDING)
            return evidence_id

    raise capture_failure
