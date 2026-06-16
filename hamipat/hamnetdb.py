"""Read host and subnet data from HamnetDB and turn it into DNS records."""
import ipaddress
import logging

import requests

from .config import HAMIP_AT, HAMNETDB_HOST_URL, HAMNETDB_SUBNET_URL
from .records import DEFAULT_TTL, RecordMap, ResourceRecord

log = logging.getLogger(__name__)

# Prefixes used, in order of preference, to choose the target of a per-site
# CNAME (e.g. oe3xnr.hamip.at. -> web.oe3xnr.hamip.at.).
SITE_TARGET_PREFIXES = ("www.", "web.", "bb.", "router.")


class HamnetDbClient:
    """Fetches HamnetDB data and builds the desired DNS record set.

    The HTTP layer is injectable (``session``) so the record-building logic can
    be unit-tested without network access.
    """

    def __init__(
        self,
        hamip_at: str = HAMIP_AT,
        host_url: str = HAMNETDB_HOST_URL,
        subnet_url: str = HAMNETDB_SUBNET_URL,
        session=None,
    ):
        self.hamip_at = hamip_at
        self.host_url = host_url
        self.subnet_url = subnet_url
        # ``requests`` itself works as the default "session" (it exposes .get).
        self.session = session or requests

    # -- public API ---------------------------------------------------------

    def fetch_hosts(self) -> RecordMap:
        """Return A/CNAME records for all Austrian (``oe*``) HamnetDB hosts."""
        records: RecordMap = {}
        entries = self._get_json(self.host_url)
        entries = [e for e in entries if e.get("site", "").startswith("oe")]

        sites = []
        for entry in entries:
            site = entry.get("site")
            if site not in sites:
                sites.append(site)
            if entry.get("deleted") != 0:
                continue
            host_name = self._add_host(records, entry)
            self._add_aliases(records, entry, host_name, site)

        self._add_site_records(records, sites)
        return records

    def fetch_dhcp(self, hosts: RecordMap) -> RecordMap:
        """Expand HamnetDB DHCP ranges into individual A records.

        ``hosts`` is the host record map (from :meth:`fetch_hosts`); it is used
        to derive the site suffix for each subnet.
        """
        ip_to_site = self._build_ip_to_site(hosts)
        dhcp: RecordMap = {}

        for entry in self._get_json(self.subnet_url):
            if entry.get("deleted") != 0:
                continue
            dhcp_range = entry.get("dhcp_range", "")
            if not dhcp_range:
                continue
            suffix = self._dhcp_suffix(entry, ip_to_site)
            if suffix is None:
                continue

            range_start, range_end = map(int, dhcp_range.split("-"))
            octets = str(ipaddress.IPv4Address(entry["begin_ip"])).split(".")
            for last_octet in range(range_start, range_end + 1):
                octets[3] = str(last_octet)
                ip = ".".join(octets)
                key = f"dhcp-{ip.replace('.', '-')}.{suffix}"
                dhcp[key] = ResourceRecord("A", ip, DEFAULT_TTL)

        return dhcp

    # -- host helpers -------------------------------------------------------

    def _add_host(self, records: RecordMap, entry: dict):
        """Add the host's A record; return its FQDN (or None)."""
        name = entry.get("name")
        ip = entry.get("ip")
        if not name:
            return None
        host_name = name + self.hamip_at
        if ip and host_name not in records:
            records[host_name] = ResourceRecord("A", ip, DEFAULT_TTL)
            # Hosts under oe0any are also exposed without the ".oe0any" segment.
            if host_name.endswith(".oe0any" + self.hamip_at):
                records.setdefault(
                    host_name.replace(".oe0any", ""),
                    ResourceRecord("A", ip, DEFAULT_TTL),
                )
        return host_name

    def _add_aliases(self, records: RecordMap, entry: dict, host_name, site):
        if not host_name:
            return
        aliases = entry.get("aliases", "")
        if not aliases:
            return
        for alias in aliases.split(","):
            alias_name = alias.strip() + self.hamip_at
            if alias_name == host_name or alias_name in records:
                continue
            records[alias_name] = ResourceRecord("CNAME", host_name, DEFAULT_TTL)
            # A "-global.<site>" alias is also exposed at the top level.
            global_suffix = "-global." + site + self.hamip_at
            if alias_name.endswith(global_suffix):
                special = alias_name.replace(global_suffix, "") + self.hamip_at
                records.setdefault(
                    special, ResourceRecord("CNAME", host_name, DEFAULT_TTL)
                )

    def _add_site_records(self, records: RecordMap, sites):
        """Add a per-site CNAME (e.g. oe3xnr.hamip.at.) pointing at a host."""
        for site in sorted(sites):
            site_domain = site + self.hamip_at
            if site_domain in records:
                continue
            target = self._pick_site_target(records, site_domain)
            if target:
                records[site_domain] = ResourceRecord("CNAME", target, DEFAULT_TTL)

    @staticmethod
    def _pick_site_target(records: RecordMap, site_domain):
        for prefix in SITE_TARGET_PREFIXES:
            candidate = prefix + site_domain
            if candidate in records and records[candidate].type == "A":
                return candidate
        # Fallback: any host under the site.
        for name in records:
            if name.endswith("." + site_domain):
                return name
        return None

    # -- dhcp helpers -------------------------------------------------------

    def _build_ip_to_site(self, hosts: RecordMap):
        ip_to_site = {}
        for name, record in hosts.items():
            if record.type != "A":
                continue
            index = name.rfind(self.hamip_at)
            site = name[name.rfind(".", 0, index - 1) + 1:]
            ip_to_site[record.content] = site
        return ip_to_site

    @staticmethod
    def _dhcp_suffix(entry: dict, ip_to_site):
        """Derive the site suffix for a subnet from one of its host IPs."""
        cidr = entry.get("ip", "")
        if not cidr:
            return None
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError as exc:
            log.warning("Error processing CIDR %s: %s", cidr, exc)
            return None
        for host_ip in network.hosts():
            site = ip_to_site.get(str(host_ip))
            if site is not None:
                return site
        return None

    # -- http ---------------------------------------------------------------

    def _get_json(self, url):
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
