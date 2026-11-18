from hashlib import sha256

from capture.freeze import capture_run
from capture.slots import CaptureError
from handoff.evidence import get_evidence
from runs.lifecycle import RunError, RunStage
from runs.register import open_run
from runs.store import load_run_record
from source.opening import RecordingError
from tests.fixtures import StationCase, end, mark, reading


class CaptureTests(StationCase):
    def test_repeated_ticks_and_first_mark_origin(self):
        source, pack = self.capture_sample('full_turn')
        self.assertEqual((pack.line_id, pack.run_id), ('ring', 'full_turn'))
        self.assertEqual(pack.origin.path, str(source.resolve()))
        self.assertEqual(pack.origin.sha256, sha256(source.read_bytes()).hexdigest())
        self.assertEqual(
            [(s.slot, s.tick, s.value, s.reading_event, s.mark, s.mark_event) for s in pack.slots],
            [(0, 0, 4, 1, 0, 2), (1, 0, 19, 3, None, None), (2, 0, 6, 4, 20, 5)],
        )
        run = load_run_record(self.db, 'ring', 'full_turn')
        self.assertEqual((run.stage, run.evidence_id), (RunStage.RECORDED, pack.evidence_id))
        self.assertEqual(self.evidence_count(), 1)

    def test_registration_conflict_and_idempotence(self):
        source = self.sample('normal')
        original = open_run(self.db, 'ring', 'morning', source)
        self.assertEqual(original.stage, RunStage.REGISTERED)
        self.assertEqual(open_run(self.db, 'ring', 'morning', source), original)
        evidence_id = capture_run(self.db, 'ring', 'morning')
        recorded = load_run_record(self.db, 'ring', 'morning')
        self.assertEqual(recorded.evidence_id, evidence_id)
        self.assertEqual(open_run(self.db, 'ring', 'morning', source), recorded)
        self.recording('normal', [reading(0, 0, 98), mark(0, 0), end()])
        with self.assertRaisesRegex(RunError, 'different recording'):
            open_run(self.db, 'ring', 'morning', source)
        with self.assertRaisesRegex(RunError, 'unknown line'):
            open_run(self.db, 'absent-line', 'morning', source)
        self.assertEqual(load_run_record(self.db, 'ring', 'morning'), recorded)
        self.assertIsNone(load_run_record(self.db, 'absent-line', 'morning'))
        with self.assertRaisesRegex(RunError, 'expected registered'):
            capture_run(self.db, 'ring', 'morning')
        self.assertEqual(self.evidence_count(), 1)

    def test_capture_rejects_replaced_source(self):
        source = self.sample('normal')
        run = open_run(self.db, 'ring', 'morning', source)
        self.recording('normal', [reading(0, 0, 95), mark(0, 0), end()])
        with self.assertRaisesRegex(RunError, 'source changed'):
            capture_run(self.db, 'ring', 'morning')
        self.assertEqual(load_run_record(self.db, 'ring', 'morning'), run)
        self.assertEqual(self.evidence_count(), 0)

    def test_invalid_slot_sets(self):
        _, original = self.capture_sample('normal')
        cases = {
            'empty': ([end()], 'no readings'),
            'skip': ([reading(0, 0, 1), mark(0, 0), reading(2, 2, 2), end()], 'slot 1'),
            'repeat': ([reading(0, 0, 1), mark(0, 0), reading(0, 0, 2), end()], 'slot 1'),
            'no-first-mark': ([reading(0, 0, 1), end()], 'first physical slot'),
            'absent-target': ([reading(0, 0, 1), mark(0, 0), mark(1, 1), end()], 'absent slot'),
        }
        for name, (events, reason) in cases.items():
            with self.subTest(name=name):
                source = self.recording(name, events)
                open_run(self.db, 'ring', name, source)
                with self.assertRaisesRegex(CaptureError, reason):
                    capture_run(self.db, 'ring', name)
                failed = load_run_record(self.db, 'ring', name)
                self.assertEqual(failed.stage, RunStage.FAILED)
                self.assertIsNone(failed.evidence_id)
                self.assertIn(reason, failed.failure)
                self.assertEqual(self.evidence_count(), 1)
                self.assertEqual(get_evidence(self.db, original.evidence_id), original)

    def test_truncated_keeps_existing_evidence(self):
        _, original = self.capture_sample('normal')
        source = self.recording('truncated', [reading(0, 0, 4), mark(0, 0), reading(1, 1, 9)])
        open_run(self.db, 'ring', 'truncated', source)
        with self.assertRaisesRegex(RecordingError, 'missing end event'):
            capture_run(self.db, 'ring', 'truncated')
        self.reopen()
        self.assertEqual(load_run_record(self.db, 'ring', 'truncated').stage, RunStage.FAILED)
        self.assertEqual(self.evidence_count(), 1)
        self.assertEqual(get_evidence(self.db, original.evidence_id), original)

    def test_end_must_be_last(self):
        for name, extra in [('trailing-reading', reading(1, 1, 6)), ('double-end', end())]:
            with self.subTest(name=name):
                source = self.recording(name, [reading(0, 0, 4), mark(0, 0), end(), extra])
                open_run(self.db, 'ring', name, source)
                with self.assertRaisesRegex(RecordingError, 'event 4: follows end event 3'):
                    capture_run(self.db, 'ring', name)
                self.assertEqual(load_run_record(self.db, 'ring', name).stage, RunStage.FAILED)
                self.assertEqual(self.evidence_count(), 0)

    def test_conflicting_marks(self):
        base = [reading(0, 0, 4), mark(0, 0), reading(1, 0, 19), mark(1, 10)]
        source = self.recording('conflict', [*base, mark(1, 20), end()])
        open_run(self.db, 'ring', 'conflict', source)
        with self.assertRaisesRegex(CaptureError, 'conflicting mark'):
            capture_run(self.db, 'ring', 'conflict')
        self.assertEqual(load_run_record(self.db, 'ring', 'conflict').stage, RunStage.FAILED)
        self.assertEqual(self.evidence_count(), 0)
        control = self.capture('consistent', self.recording('consistent', [*base, end()]))
        self.assertEqual(control.slots[1].mark, 10)

    def test_malformed_device_events(self):
        cases = [b'\xff', b'{', b'[]', b'{"kind":"reading","slot":0,"tick":0,"value":true}',
                 b'{"kind":"reading","slot":0,"tick":10,"value":3}',
                 b'{"kind":"reading","slot":0,"tick":0}',
                 b'{"kind":"end","kind":"end"}']
        for index, invalid in enumerate(cases):
            with self.subTest(index=index):
                name = f'malformed-{index}'
                source = self.root / f'{name}.jsonl'
                source.write_bytes(invalid + b'\n{"kind":"end"}\n')
                open_run(self.db, 'ring', name, source)
                with self.assertRaisesRegex(RecordingError, 'event 1:'):
                    capture_run(self.db, 'ring', name)
                self.assertEqual(load_run_record(self.db, 'ring', name).stage, RunStage.FAILED)
        self.assertEqual(self.evidence_count(), 0)
