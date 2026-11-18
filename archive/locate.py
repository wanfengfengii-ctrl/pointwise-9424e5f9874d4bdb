from dataclasses import dataclass

from capture.packs import EvidencePack
from source.events import TURN_LENGTH

MAX_STEP = 10
MAX_STEP_CHANGE = 10


class NoTrajectory(ValueError):
    """The recorded evidence admits no complete physical trajectory."""


@dataclass(frozen=True, slots=True)
class LocationAssessment:
    positions: tuple[int | None, ...]


def _step_offsets(previous_tick: int, tick: int) -> tuple[int, ...]:
    """Signed displacements that keep the coordinate congruent to tick mod 10."""
    forward = (tick - previous_tick) % TURN_LENGTH
    offsets = [forward - TURN_LENGTH, forward]
    if forward == 0:
        offsets.append(TURN_LENGTH)
    return tuple(offset for offset in offsets if abs(offset) <= MAX_STEP)


def assess_trajectory(pack: EvidencePack) -> LocationAssessment:
    slots = pack.slots
    first = slots[0]
    if first.mark is None or first.mark % TURN_LENGTH != first.tick:
        raise NoTrajectory("first mark and tick cannot describe the same location")
    for slot in slots[1:]:
        if slot.mark is not None and slot.mark % TURN_LENGTH != slot.tick:
            raise NoTrajectory(f"mark and tick disagree at slot {slot.slot}")

    # Forward pass: states at a slot are (coordinate, signed step that arrived there).
    states: list[set[tuple[int, int | None]]] = [{(first.mark, None)}]
    for index in range(1, len(slots)):
        slot = slots[index]
        arrived: set[tuple[int, int | None]] = set()
        for position, step in states[-1]:
            if slot.mark is not None:
                candidates = (slot.mark - position,)
            else:
                candidates = _step_offsets(slots[index - 1].tick, slot.tick)
            for offset in candidates:
                if abs(offset) > MAX_STEP:
                    continue
                if step is not None and abs(offset - step) > MAX_STEP_CHANGE:
                    continue
                arrived.add((position + offset, offset))
        states.append(arrived)

    if not states[-1]:
        raise NoTrajectory('no complete trajectory satisfies the recorded evidence')

    # Backward pass: keep only states that can still reach the final slot.
    viable: list[set[tuple[int, int | None]]] = [states[-1]]
    for index in range(len(slots) - 2, -1, -1):
        reachable: set[tuple[int, int | None]] = set()
        for position, step in states[index]:
            for next_position, next_step in viable[0]:
                if next_position - position != next_step:
                    continue
                if step is not None and abs(next_step - step) > MAX_STEP_CHANGE:
                    continue
                reachable.add((position, step))
        viable.insert(0, reachable)

    positions = []
    for index in range(len(slots)):
        supported = {position for position, _ in viable[index]}
        positions.append(supported.pop() if len(supported) == 1 else None)
    return LocationAssessment(tuple(positions))
