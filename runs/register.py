from pathlib import Path
from sqlite3 import Connection

from runs.lifecycle import RunError, RunRecord
from runs.lines import find_line
from runs.store import insert_run_record, load_run_record, write_transaction
from source.opening import open_recording


def open_run(db: Connection, line_id: str, run_id: str, source: str | Path) -> RunRecord:
    if not isinstance(line_id, str) or not line_id.strip():
        raise RunError('line ID must be nonempty text')
    if not isinstance(run_id, str) or not run_id.strip():
        raise RunError('run ID must be nonempty text')

    with write_transaction(db):
        if find_line(db, line_id) is None:
            raise RunError(f'unknown line {line_id!r}')
        origin = open_recording(source).origin
        existing = load_run_record(db, line_id, run_id)
        if existing is not None:
            if existing.origin != origin:
                raise RunError(f'run {line_id}/{run_id} already belongs to a different recording')
            return existing
        record = RunRecord(line_id, run_id, origin)
        insert_run_record(db, record)
        return record
