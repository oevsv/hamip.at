"""Client for the PowerDNS authoritative HTTP API."""
import json
import logging

import requests

from .config import ZONE_NAME
from .records import RecordMap, ResourceRecord

log = logging.getLogger(__name__)


class PowerDnsError(Exception):
    """Raised when the PowerDNS API returns an unexpected response."""


class PowerDnsClient:
    """Thin object wrapper around the PowerDNS zone API for a single zone."""

    # Record types this tooling manages; SOA/NS and others are left untouched.
    MANAGED_TYPES = ("A", "CNAME", "TXT")

    def __init__(self, endpoint, api_key, zone=ZONE_NAME, session=None, chunk_size=500):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.zone = zone
        self.session = session or requests
        self.chunk_size = chunk_size

    @property
    def zone_url(self):
        return f"{self.endpoint}/v1/servers/localhost/zones/{self.zone}"

    def _headers(self, with_content_type=False):
        headers = {"X-API-Key": self.api_key}
        if with_content_type:
            headers["Content-Type"] = "application/json"
        return headers

    # -- reads --------------------------------------------------------------

    def fetch_zone(self) -> dict:
        """Return the raw zone document (metadata + rrsets)."""
        response = self.session.get(self.zone_url, headers=self._headers())
        if not response.ok:
            raise PowerDnsError(
                f"Error fetching zone ({response.status_code}): {response.text}"
            )
        return response.json()

    @classmethod
    def parse_records(cls, zone: dict) -> RecordMap:
        """Extract the managed records from a raw zone document."""
        records: RecordMap = {}
        for rrset in zone.get("rrsets", []):
            rrtype = rrset.get("type")
            if rrtype not in cls.MANAGED_TYPES:
                continue
            name = rrset.get("name")
            ttl = rrset.get("ttl")
            for record in rrset.get("records", []):
                records[name] = ResourceRecord(rrtype, record.get("content"), ttl)
        return records

    def fetch_records(self) -> RecordMap:
        return self.parse_records(self.fetch_zone())

    # -- writes -------------------------------------------------------------

    def replace_records(self, records: RecordMap):
        """REPLACE (add/update) the given records, in chunks."""
        self._patch(records, delete=False)

    def delete_records(self, records: RecordMap):
        """DELETE the given records, in chunks."""
        self._patch(records, delete=True)

    def increase_serial(self):
        """Bump the zone's SOA serial via the API."""
        payload = {"soa_edit_api": "INCREASE"}
        response = self.session.put(
            self.zone_url, headers=self._headers(True), data=json.dumps(payload)
        )
        if response.status_code != 204:
            raise PowerDnsError(
                f"Failed to update serial ({response.status_code}): {response.text}"
            )
        log.info("Zone serial updated.")

    # -- internals ----------------------------------------------------------

    def _patch(self, records: RecordMap, delete: bool):
        items = list(records.items())
        for start in range(0, len(items), self.chunk_size):
            chunk = items[start:start + self.chunk_size]
            rrsets = [self._rrset(name, record, delete) for name, record in chunk]
            if rrsets:
                self._send_patch({"rrsets": rrsets})

    @staticmethod
    def _rrset(name, record: ResourceRecord, delete: bool):
        if delete:
            return {"name": name, "type": record.type, "changetype": "DELETE"}
        return {
            "name": name,
            "type": record.type,
            "ttl": record.ttl,
            "changetype": "REPLACE",
            "records": [{"content": record.content, "disabled": False}],
        }

    def _send_patch(self, payload):
        response = self.session.patch(
            self.zone_url, headers=self._headers(True), data=json.dumps(payload)
        )
        if response.status_code != 204:
            raise PowerDnsError(
                f"Failed to patch ({response.status_code}): {response.text}"
            )
        return response
