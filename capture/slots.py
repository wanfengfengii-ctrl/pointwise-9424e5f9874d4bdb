from dataclasses import dataclass

from source.events import ReadingEvent


class CaptureError(ValueError):
    """Readings and marks cannot be frozen into evidence."""


@dataclass(frozen=True, slots=True)
class SlotReading:
    slot: int
    tick: int
    value: int
    event_number: int


class SlotLedger:
    def __init__(self) -> None:
        self._readings: list[SlotReading] = []

    def accept(self, event: ReadingEvent) -> None:
        expected = len(self._readings)
        if event.slot != expected:
            raise CaptureError(f'event {event.number}: expected physical slot {expected}')
        self._readings.append(SlotReading(event.slot, event.tick, event.value, event.number))

    def readings(self) -> tuple[SlotReading, ...]:
        return tuple(self._readings)
