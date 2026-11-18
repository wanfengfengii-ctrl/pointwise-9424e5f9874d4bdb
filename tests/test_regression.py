from archive.issue import issue_manifest
from archive.locate import NoTrajectory
from handoff.evidence import get_evidence
from tests.fixtures import StationCase, end, mark, reading


class CaptureRegressionTests(StationCase):
    def test_same_tick_slots_and_late_marks_stay_independent(self):
        # Slots 1 and 2 share tick 2; the unmarked slot must survive freezing.
        # Marks may arrive before or after their slot's reading and bind by slot.
        # A same-value resend keeps the first event number.
        source = self.recording('late-marks', [
            reading(0, 1, 31),
            mark(2, 22),
            reading(1, 2, 41),
            reading(2, 2, 51),
            mark(0, 11),
            mark(0, 11),
            end(),
        ])
        pack = self.capture('late-marks', source)
        self.assertEqual(
            [(s.slot, s.tick, s.value, s.reading_event, s.mark, s.mark_event) for s in pack.slots],
            [(0, 1, 31, 1, 11, 5), (1, 2, 41, 3, None, None), (2, 2, 51, 4, 22, 2)],
        )
        source.unlink()
        delivered = issue_manifest(self.db, get_evidence(self.db, pack.evidence_id))
        self.assertEqual([row.position for row in delivered.manifest.rows], [11, 12, 22])


class TrajectoryRegressionTests(StationCase):
    def issue_events(self, name, events):
        source = self.recording(name, events)
        pack = self.capture(name, source)
        source.unlink()
        return pack, issue_manifest(self.db, get_evidence(self.db, pack.evidence_id))

    def test_gentle_reversal_and_stay_are_confirmed(self):
        # Steps 10, 0, -10: adjacent changes are 10 and 10, so the unmarked
        # slot is confirmed at 10 even though the probe stays and reverses.
        _, delivered = self.issue_events('reversal', [
            reading(0, 0, 1), mark(0, 0),
            reading(1, 0, 2), mark(1, 10),
            reading(2, 0, 3),
            reading(3, 0, 4), mark(3, 0),
            end(),
        ])
        self.assertEqual(
            [(row.slot, row.value, row.position) for row in delivered.manifest.rows],
            [(0, 1, 0), (1, 2, 10), (2, 3, 10), (3, 4, 0)],
        )

    def test_sharp_reversal_is_rejected_without_publication(self):
        # Steps 10 then -10 differ by 20, beyond the allowed change of 10.
        source = self.recording('sharp', [
            reading(0, 0, 1), mark(0, 0),
            reading(1, 0, 2), mark(1, 10),
            reading(2, 0, 3), mark(2, 0),
            end(),
        ])
        pack = self.capture('sharp', source)
        source.unlink()
        with self.assertRaises(NoTrajectory):
            issue_manifest(self.db, get_evidence(self.db, pack.evidence_id))
        self.assertEqual(self.publication_counts(), (0, 0, 0))
        self.assertEqual(get_evidence(self.db, pack.evidence_id), pack)

    def test_step_change_boundary_of_ten_is_accepted(self):
        # Steps 0 then 10 differ by exactly 10 and must not be rejected.
        _, delivered = self.issue_events('boundary', [
            reading(0, 0, 5), mark(0, 0),
            reading(1, 0, 6), mark(1, 0),
            reading(2, 0, 7), mark(2, 10),
            end(),
        ])
        self.assertEqual([row.position for row in delivered.manifest.rows], [0, 0, 10])
