from capture.marks import MarkLedger
from capture.slots import CaptureError, SlotLedger
from source.events import Event, MarkEvent, ReadingEvent


class CaptureSession:
    def __init__(self) -> None:
        self.slots = SlotLedger()
        self.marks = MarkLedger()

    def accept(self, event: Event) -> None:
        if isinstance(event, ReadingEvent):
            self.slots.accept(event)
        elif isinstance(event, MarkEvent):
            self.marks.accept(event)

    def check_ready(self) -> None:
        readings = self.slots.readings()
        if not readings:
            raise CaptureError('recording contains no readings')
        self.marks.check_targets(len(readings))
