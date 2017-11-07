from enum import auto, Enum, unique


@unique
class ResourceStatus(Enum):
    MISSING = auto()
    INVALID = auto()
    STALE = auto()
    VALID = auto()
