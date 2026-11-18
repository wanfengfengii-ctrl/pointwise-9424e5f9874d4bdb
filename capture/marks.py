from dataclasses import dataclass

from capture.slots import CaptureError
from source.events import MarkEvent


@dataclass(frozen=True, slots=True)
class SlotMark:
    slot: int
    position: int
    event_number: int


class MarkLedger:
    def __init__(self) -> None:
        self._marks: dict[int, SlotMark] = {}

    def accept(self, event: MarkEvent) -> None:
        existing = self._marks.get(event.slot)
        if existing is None:
            self._marks[event.slot] = SlotMark(event.slot, event.position, event.number)
        elif existing.position != event.position:
            raise CaptureError(
                f'event {event.number}: conflicting mark for slot from event {existing.event_number}'
            )

    def for_slot(self, slot: int) -> SlotMark | None:
        return self._marks.get(slot)

    def check_targets(self, slot_count: int) -> None:
        for mark in self._marks.values():
            if not 0 <= mark.slot < slot_count:
                raise CaptureError(f'event {mark.event_number}: mark references an absent slot')
        if 0 not in self._marks:
            raise CaptureError('first physical slot requires an absolute mark')
