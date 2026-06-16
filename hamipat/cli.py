"""Command-line entry point: update the hamip.at zone(s) from HamnetDB."""
import logging
import sys
from datetime import datetime

from .config import (
    DEFAULT_TARGETS,
    STATIC_ZONES_LOCATION,
    USE_DHCP,
    read_api_key,
)
from .hamnetdb import HamnetDbClient
from .powerdns import PowerDnsClient
from .records import ResourceRecord
from .static_records import load_static_records
from .updater import ZoneUpdater

log = logging.getLogger(__name__)


def build_hamnetdb_records(client=None):
    """Build the HamnetDB-derived record set (hosts and, optionally, DHCP)."""
    client = client or HamnetDbClient()
    records = client.fetch_hosts()
    if USE_DHCP:
        records |= client.fetch_dhcp(records)
    return records


def _timestamp_record():
    """A TXT record that changes every run, ensuring the serial advances."""
    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d_%H-%M-%S") + f"_{now.microsecond // 1000:03d}"
    return {"timestamp.hamip.at.": ResourceRecord(type="TXT", content=f'"{stamp}"', ttl=60)}


def run(targets=DEFAULT_TARGETS, static_path=STATIC_ZONES_LOCATION):
    """Update every target zone from HamnetDB + static records."""
    hamnetdb_records = build_hamnetdb_records()
    static_isp, static_hamnet = load_static_records(static_path)

    for target in targets:
        api_key = read_api_key(target.api_key_path)
        if api_key is None:
            log.error("Key not found at %s or could not be read.", target.api_key_path)
            sys.exit(1)

        static = static_hamnet if target.is_hamnet else static_isp
        reference = hamnetdb_records | static | _timestamp_record()

        log.info("Updating %s zone (%s)", target.name, target.endpoint)
        client = PowerDnsClient(target.endpoint, api_key)
        ZoneUpdater(client).sync(reference)


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run()


if __name__ == "__main__":
    main()
