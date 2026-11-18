import shutil
import sys
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from archive.issue import issue_manifest
from capture.freeze import capture_run
from handoff.evidence import get_evidence
from handoff.lookup import get_manifest
from runs.register import open_run
from runs.store import initialize_store, open_store
from source.format import encode_json


class CaptureMismatch(Exception):
    def __init__(self, step, expected, actual):
        self.details = {'step': step, 'expected': expected, 'actual': actual}


def require_equal(step, expected, actual):
    if actual != expected:
        raise CaptureMismatch(step, expected, actual)


def delivery_rows(delivery):
    if delivery is None:
        return None
    return [(row.slot, row.tick, row.value, row.position) for row in delivery.manifest.rows]


def verify():
    sample = Path(__file__).resolve().parent / 'samples' / 'full_turn.jsonl'
    expected = [(0, 0, 4, 0, 2), (1, 0, 19, None, None), (2, 0, 6, 20, 5)]
    expected_rows = [(0, 0, 4, 0), (1, 0, 19, 10), (2, 0, 6, 20)]

    with TemporaryDirectory(prefix='track-verify-') as directory:
        root = Path(directory)
        db_path = root / 'station.sqlite'
        source = root / sample.name
        shutil.copyfile(sample, source)
        with closing(open_store(db_path)) as db:
            initialize_store(db)
            open_run(db, 'ring', 'full-turn-check', source)
            evidence_id = capture_run(db, 'ring', 'full-turn-check')
            pack = get_evidence(db, evidence_id)
            actual = None if pack is None else [
                (slot.slot, slot.tick, slot.value, slot.mark, slot.mark_event) for slot in pack.slots
            ]
            require_equal('frozen evidence', expected, actual)

        source.unlink()
        with closing(open_store(db_path)) as db:
            detached = get_evidence(db, evidence_id)
            require_equal('offline evidence number', evidence_id, detached.evidence_id if detached else None)
            issued = issue_manifest(db, detached)
            require_equal('issued rows', expected_rows, delivery_rows(issued))
            require_equal('receipt evidence', evidence_id, issued.receipt.evidence_id)
            require_equal('receipt manifest', issued.manifest.manifest_id, issued.receipt.manifest_id)

        with closing(open_store(db_path)) as db:
            retrieved = get_manifest(db, issued.manifest.manifest_id)
            actual_rows = delivery_rows(retrieved)
            require_equal('reopened rows', expected_rows, actual_rows)
            require_equal('reopened evidence', evidence_id, retrieved.manifest.evidence_id)
            require_equal('reopened receipt number', issued.receipt.manifest_id, retrieved.receipt.manifest_id)
            require_equal('reopened receipt evidence', evidence_id, retrieved.receipt.evidence_id)

        print('POINTWISE_SCENARIO ' + encode_json({
            'case_id': 'v_full_turn',
            'input': {'sample': 'samples/full_turn.jsonl', 'ticks': [0, 0, 0],
                      'values': [4, 19, 6], 'marks': {'0': 0, '2': 20}},
            'expected': expected,
            'actual': actual,
            'downstream_expected': expected_rows,
            'downstream_actual': actual_rows,
            'code_paths': ['capture/freeze.py', 'archive/locate.py', 'archive/issue.py', 'handoff/lookup.py'],
            'oracle': 'Two steps of at most 10 must sum to 20, so both are 10. The recording lists three distinct slots and the first final mark is event 5.',
        }))


def main():
    try:
        verify()
    except CaptureMismatch as error:
        print('TRACE_CAPTURE_MISMATCH ' + encode_json(error.details), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
