"""The DNS resource-record value object."""
from dataclasses import dataclass
from typing import Dict

DEFAULT_TTL = 600


@dataclass(frozen=True)
class ResourceRecord:
    """An immutable DNS resource record.

    Records are compared by value (type, content, ttl), which is what the zone
    diffing in :class:`~hamipat.updater.ZoneUpdater` relies on.
    """

    type: str
    content: str
    ttl: int = DEFAULT_TTL


# A zone is represented throughout the package as a mapping of FQDN -> record.
RecordMap = Dict[str, ResourceRecord]
