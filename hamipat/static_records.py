"""Load locally maintained static records from YAML."""
import logging

import yaml

from .records import RecordMap, ResourceRecord

log = logging.getLogger(__name__)


def load_static_records(path):
    """Load static records from a YAML file.

    The file has top-level ``isp:`` and ``hamnet:`` sections, each mapping an
    FQDN to a record (``type``, ``content``, ``ttl``). Returns a
    ``(isp, hamnet)`` tuple of record maps, or two empty maps on any error.
    """
    try:
        with open(path, "r") as handle:
            data = yaml.safe_load(handle)
        return _section(data, "isp"), _section(data, "hamnet")
    except Exception as exc:  # noqa: BLE001 - loading is best-effort
        log.warning("Error loading static zones from %s: %s", path, exc)
        return {}, {}


def _section(data, key) -> RecordMap:
    return {
        name: ResourceRecord(type=entry["type"], content=entry["content"], ttl=entry["ttl"])
        for name, entry in data[key].items()
    }
