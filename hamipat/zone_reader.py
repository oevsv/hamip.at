"""Read a DNS zone over AXFR (utility / diagnostics)."""
import logging

import dns.query
import dns.rdataclass
import dns.rdatatype
import dns.zone

from .config import ZONE_NAME

log = logging.getLogger(__name__)


def load_dns_zone(zone_name, nameserver, port=53):
    """Return all records of ``zone_name`` via AXFR as a tuple of tuples.

    Each record is ``(name, ttl, class, type, value)``. Returns an empty tuple
    if the transfer fails.
    """
    try:
        zone = dns.zone.from_xfr(dns.query.xfr(nameserver, zone_name, port=port))
    except Exception as exc:  # noqa: BLE001 - diagnostics helper
        log.warning("Failed to load DNS zone: %s", exc)
        return ()

    records = []
    for name, node in zone.nodes.items():
        for rdataset in node.rdatasets:
            record_class = dns.rdataclass.to_text(rdataset.rdclass)
            record_type = dns.rdatatype.to_text(rdataset.rdtype)
            for rdata in rdataset:
                records.append(
                    (name.to_text(), rdataset.ttl, record_class, record_type, rdata.to_text())
                )
    return tuple(records)


def main():
    nameserver = "44.143.0.10"
    for name, ttl, rclass, rtype, value in load_dns_zone(ZONE_NAME, nameserver):
        print(f"{name:<30} {ttl:<6} {rclass:<5} {rtype:<6} {value}")


if __name__ == "__main__":
    main()
