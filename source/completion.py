from source.events import EndEvent, Event
from source.opening import RecordingError


class ReplayCompletion:
    def __init__(self) -> None:
        self._end_number: int | None = None

    def observe(self, event: Event) -> None:
        if self._end_number is not None:
            raise RecordingError(f'event {event.number}: follows end event {self._end_number}')
        if isinstance(event, EndEvent):
            self._end_number = event.number

    def finish(self) -> None:
        if self._end_number is None:
            raise RecordingError('truncated recording: missing end event')
