import enum
from dataclasses import dataclass

class LinkEventType(enum.Enum):
    NopEvent     = enum.auto()
    FailureEvent  = enum.auto()
    RecoveryEvent = enum.auto()

@dataclass
class LinkEvent:
    time: int
    type: LinkEventType
    link_id: int
    loss_rate: float
