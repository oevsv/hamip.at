"""hamip.at — build and maintain the hamip.at DNS zone from HamnetDB.

The package is organised around a few small, single-responsibility pieces:

- :class:`~hamipat.records.ResourceRecord` — the DNS record value object.
- :class:`~hamipat.hamnetdb.HamnetDbClient` — reads HamnetDB and builds records.
- :class:`~hamipat.powerdns.PowerDnsClient` — talks to the PowerDNS HTTP API.
- :class:`~hamipat.updater.ZoneUpdater` — diffs a desired record set against a
  live zone and applies the changes.
- :mod:`hamipat.cli` — wires everything together (the command-line entry point).
"""
from .records import ResourceRecord

__all__ = ["ResourceRecord"]
__version__ = "0.1.0"
