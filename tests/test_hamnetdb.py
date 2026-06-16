"""Unit tests for HamnetDbClient record building (HTTP layer is faked)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hamipat.hamnetdb import HamnetDbClient  # noqa: E402
from hamipat.records import ResourceRecord  # noqa: E402

HAMIP_AT = ".hamip.at."


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeSession:
    """Returns the same canned payload for every GET."""

    def __init__(self, payload):
        self._payload = payload

    def get(self, *args, **kwargs):
        return FakeResponse(self._payload)


def client_for(payload):
    return HamnetDbClient(session=FakeSession(payload))


class TestFetchHosts(unittest.TestCase):

    def test_a_record_and_alias_cname(self):
        entries = [{
            "site": "oe3xnr", "name": "web.oe3xnr", "ip": "44.143.60.66",
            "deleted": 0, "aliases": "www.oe3xnr,aprs.oe3xnr",
        }]
        records = client_for(entries).fetch_hosts()
        self.assertEqual(records["web.oe3xnr.hamip.at."],
                         ResourceRecord(type="A", content="44.143.60.66", ttl=600))
        self.assertEqual(records["www.oe3xnr.hamip.at."],
                         ResourceRecord(type="CNAME", content="web.oe3xnr.hamip.at.", ttl=600))
        self.assertEqual(records["aprs.oe3xnr.hamip.at."],
                         ResourceRecord(type="CNAME", content="web.oe3xnr.hamip.at.", ttl=600))

    def test_site_cname_prefers_web_over_alias(self):
        entries = [{
            "site": "oe3xnr", "name": "web.oe3xnr", "ip": "44.143.60.66",
            "deleted": 0, "aliases": "www.oe3xnr",
        }]
        records = client_for(entries).fetch_hosts()
        self.assertEqual(records["oe3xnr.hamip.at."],
                         ResourceRecord(type="CNAME", content="web.oe3xnr.hamip.at.", ttl=600))

    def test_site_cname_fallback_to_any_prefix(self):
        entries = [{
            "site": "oe3xyz", "name": "gw.oe3xyz", "ip": "44.143.1.1",
            "deleted": 0, "aliases": "",
        }]
        records = client_for(entries).fetch_hosts()
        self.assertEqual(records["oe3xyz.hamip.at."],
                         ResourceRecord(type="CNAME", content="gw.oe3xyz.hamip.at.", ttl=600))

    def test_deleted_entries_are_skipped(self):
        entries = [{
            "site": "oe3xnr", "name": "old.oe3xnr", "ip": "44.143.60.99",
            "deleted": 1, "aliases": "",
        }]
        records = client_for(entries).fetch_hosts()
        self.assertNotIn("old.oe3xnr.hamip.at.", records)

    def test_non_austrian_sites_filtered_out(self):
        entries = [{
            "site": "db0abc", "name": "web.db0abc", "ip": "44.130.1.1",
            "deleted": 0, "aliases": "",
        }]
        records = client_for(entries).fetch_hosts()
        self.assertEqual(records, {})

    def test_oe0any_special_host(self):
        entries = [{
            "site": "oe0any", "name": "test.oe0any", "ip": "44.143.0.7",
            "deleted": 0, "aliases": "",
        }]
        records = client_for(entries).fetch_hosts()
        self.assertEqual(records["test.oe0any.hamip.at."],
                         ResourceRecord(type="A", content="44.143.0.7", ttl=600))
        self.assertEqual(records["test.hamip.at."],
                         ResourceRecord(type="A", content="44.143.0.7", ttl=600))


class TestFetchDhcp(unittest.TestCase):

    def test_dhcp_range_expansion(self):
        hosts = {
            "router.oe3xnr.hamip.at.": ResourceRecord(type="A", content="44.143.60.40", ttl=600),
        }
        subnets = [{
            "deleted": 0,
            "ip": "44.143.60.32/28",
            "begin_ip": 747584544,  # 44.143.60.32
            "dhcp_range": "35-37",
        }]
        dhcp = client_for(subnets).fetch_dhcp(hosts)
        self.assertEqual(dhcp["dhcp-44-143-60-35.oe3xnr.hamip.at."],
                         ResourceRecord(type="A", content="44.143.60.35", ttl=600))
        self.assertEqual(dhcp["dhcp-44-143-60-37.oe3xnr.hamip.at."],
                         ResourceRecord(type="A", content="44.143.60.37", ttl=600))
        self.assertEqual(len(dhcp), 3)


if __name__ == "__main__":
    unittest.main()
