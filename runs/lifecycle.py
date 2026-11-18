from dataclasses import dataclass, replace
from enum import StrEnum

from source.opening import RecordingOrigin


class RunError(ValueError):
    """A registration or capture request cannot use the specified run."""


class RunStage(StrEnum):
    REGISTERED = 'registered'
    RECORDING = 'recording'
    RECORDED = 'recorded'
    FAILED = 'failed'


@dataclass(frozen=True, slots=True)
class RunRecord:
    line_id: str
    run_id: str
    origin: RecordingOrigin
    stage: RunStage = RunStage.REGISTERED
    evidence_id: int | None = None
    failure: str | None = None

    def _require(self, expected: RunStage) -> None:
        if self.stage != expected:
            raise RunError(f'run {self.line_id}/{self.run_id} is {self.stage}, expected {expected}')

    def begin_recording(self) -> 'RunRecord':
        self._require(RunStage.REGISTERED)
        return replace(self, stage=RunStage.RECORDING)

    def finish_recording(self, evidence_id: int) -> 'RunRecord':
        self._require(RunStage.RECORDING)
        return replace(self, stage=RunStage.RECORDED, evidence_id=evidence_id)

    def fail_recording(self, reason: str) -> 'RunRecord':
        self._require(RunStage.RECORDING)
        return replace(self, stage=RunStage.FAILED, failure=reason)
