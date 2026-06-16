"""Diff a desired record set against a live zone and apply the changes."""
import logging

from .powerdns import PowerDnsError
from .records import RecordMap

log = logging.getLogger(__name__)


class ZoneUpdater:
    """Reconciles a live PowerDNS zone with a desired set of records."""

    def __init__(self, client):
        self.client = client

    def sync(self, reference: RecordMap):
        """Make the zone match ``reference``.

        Returns the ``(to_remove, to_change)`` maps that were applied.
        """
        zone = self.client.fetch_zone()
        serial = zone.get("serial")
        if serial is None:
            raise PowerDnsError("Zone metadata has no serial")
        log.info("Current serial: %s", serial)

        current = self.client.parse_records(zone)
        if not current:
            raise PowerDnsError("No records returned from server")

        # Anything on the server that is absent from or differs from the
        # reference is removed; anything new or changed in the reference is
        # (re)applied.
        to_remove = {
            name: record
            for name, record in current.items()
            if reference.get(name) != record
        }
        to_change = {
            name: record
            for name, record in reference.items()
            if current.get(name) != record
        }

        log.info("Keys to be removed: %d", len(to_remove))
        self.client.delete_records(to_remove)

        log.info("Keys to be changed or added: %d", len(to_change))
        self.client.replace_records(to_change)

        self.client.increase_serial()
        return to_remove, to_change
