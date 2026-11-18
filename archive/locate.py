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


def assess_trajectory(pack: EvidencePack) -> LocationAssessment:
    first = pack.slots[0]
    position = first.mark
    if position is None or position % TURN_LENGTH != first.tick:
        raise NoTrajectory("first mark and tick cannot describe the same location")

    positions = [position]
    for slot in pack.slots[1:]:
        if slot.mark is not None:
            if slot.mark % TURN_LENGTH != slot.tick:
                raise NoTrajectory(f"mark and tick disagree at slot {slot.slot}")
            position = slot.mark
        else:
            forward = (slot.tick - position) % TURN_LENGTH
            backward = forward - TURN_LENGTH
            position += forward if forward <= -backward else backward
        positions.append(position)
    return LocationAssessment(tuple(positions))
