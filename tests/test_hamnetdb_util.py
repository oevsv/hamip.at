"""Unit tests for hamnetdb_util record building (network calls are mocked)."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hamip.at"))

import hamnetdb_util  # noqa: E402
from hamnetdb_util import get_hamnetdb_hosts, get_hamnetdb_dhcp, Resource_record  # noqa: E402

HAMIP_AT = ".hamip.at."


class FakeResponse:
    """Minimal stand-in for a requests.Response."""

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def fake_get(payload):
    return lambda *args, **kwargs: FakeResponse(payload)


class TestGetHamnetdbHosts(unittest.TestCase):

    def _build(self, entries):
        result = {}
        with patch.object(hamnetdb_util.requests, "get", fake_get(entries)):
            get_hamnetdb_hosts(result, HAMIP_AT)
        return result

    def test_a_record_and_alias_cname(self):
        entries = [{
            "site": "oe3xnr", "name": "web.oe3xnr", "ip": "44.143.60.66",
            "deleted": 0, "aliases": "www.oe3xnr,aprs.oe3xnr",
        }]
        result = self._build(entries)
        self.assertEqual(result["web.oe3xnr.hamip.at."],
                         Resource_record(type="A", content="44.143.60.66", ttl=600))
        self.assertEqual(result["www.oe3xnr.hamip.at."],
                         Resource_record(type="CNAME", content="web.oe3xnr.hamip.at.", ttl=600))
        self.assertEqual(result["aprs.oe3xnr.hamip.at."],
                         Resource_record(type="CNAME", content="web.oe3xnr.hamip.at.", ttl=600))

    def test_site_cname_prefers_web_over_alias(self):
        # The per-site name must point at an A record (web.), not at the CNAME alias www.
        entries = [{
            "site": "oe3xnr", "name": "web.oe3xnr", "ip": "44.143.60.66",
            "deleted": 0, "aliases": "www.oe3xnr",
        }]
        result = self._build(entries)
        self.assertEqual(result["oe3xnr.hamip.at."],
                         Resource_record(type="CNAME", content="web.oe3xnr.hamip.at.", ttl=600))

    def test_site_cname_fallback_to_any_prefix(self):
        entries = [{
            "site": "oe3xyz", "name": "gw.oe3xyz", "ip": "44.143.1.1",
            "deleted": 0, "aliases": "",
        }]
        result = self._build(entries)
        self.assertEqual(result["oe3xyz.hamip.at."],
                         Resource_record(type="CNAME", content="gw.oe3xyz.hamip.at.", ttl=600))

    def test_deleted_entries_are_skipped(self):
        entries = [{
            "site": "oe3xnr", "name": "old.oe3xnr", "ip": "44.143.60.99",
            "deleted": 1, "aliases": "",
        }]
        result = self._build(entries)
        self.assertNotIn("old.oe3xnr.hamip.at.", result)

    def test_non_austrian_sites_filtered_out(self):
        entries = [{
            "site": "db0abc", "name": "web.db0abc", "ip": "44.130.1.1",
            "deleted": 0, "aliases": "",
        }]
        result = self._build(entries)
        self.assertEqual(result, {})

    def test_oe0any_special_host(self):
        entries = [{
            "site": "oe0any", "name": "test.oe0any", "ip": "44.143.0.7",
            "deleted": 0, "aliases": "",
        }]
        result = self._build(entries)
        self.assertEqual(result["test.oe0any.hamip.at."],
                         Resource_record(type="A", content="44.143.0.7", ttl=600))
        # the ".oe0any" segment is dropped to expose a top-level name
        self.assertEqual(result["test.hamip.at."],
                         Resource_record(type="A", content="44.143.0.7", ttl=600))


class TestGetHamnetdbDhcp(unittest.TestCase):

    def test_dhcp_range_expansion(self):
        hosts_dict = {
            "router.oe3xnr.hamip.at.": Resource_record(type="A", content="44.143.60.40", ttl=600),
        }
        subnets = [{
            "deleted": 0,
            "ip": "44.143.60.32/28",
            "begin_ip": 747584544,  # 44.143.60.32
            "dhcp_range": "35-37",
        }]
        dhcp_dict = {}
        with patch.object(hamnetdb_util.requests, "get", fake_get(subnets)):
            get_hamnetdb_dhcp(dhcp_dict, hosts_dict, HAMIP_AT)

        # Suffix is derived from the matching host's site (oe3xnr).
        self.assertEqual(dhcp_dict["dhcp-44-143-60-35.oe3xnr.hamip.at."],
                         Resource_record(type="A", content="44.143.60.35", ttl=600))
        self.assertEqual(dhcp_dict["dhcp-44-143-60-37.oe3xnr.hamip.at."],
                         Resource_record(type="A", content="44.143.60.37", ttl=600))
        self.assertEqual(len(dhcp_dict), 3)


if __name__ == "__main__":
    unittest.main()
