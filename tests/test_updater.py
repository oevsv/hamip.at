"""Unit tests for the ZoneUpdater diff/apply logic."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hamipat.powerdns import PowerDnsClient, PowerDnsError  # noqa: E402
from hamipat.records import ResourceRecord  # noqa: E402
from hamipat.updater import ZoneUpdater  # noqa: E402


def rr(content):
    return ResourceRecord("A", content, 600)


class FakeClient:
    """Stands in for PowerDnsClient, capturing the applied changes."""

    def __init__(self, current, serial=1):
        self._current = current
        self._serial = serial
        self.deleted = None
        self.replaced = None
        self.serial_bumped = False

    def fetch_zone(self):
        return {"serial": self._serial}

    # ZoneUpdater calls parse_records on whatever fetch_zone returned; reuse the
    # real (static) implementation, but return our canned record set.
    def parse_records(self, zone):
        return dict(self._current)

    def delete_records(self, records):
        self.deleted = records

    def replace_records(self, records):
        self.replaced = records

    def increase_serial(self):
        self.serial_bumped = True


class TestZoneUpdaterSync(unittest.TestCase):

    def test_diff_computes_removals_and_changes(self):
        current = {
            "keep.hamip.at.": rr("1.1.1.1"),
            "old.hamip.at.": rr("2.2.2.2"),
            "change.hamip.at.": rr("3.3.3.3"),
        }
        reference = {
            "keep.hamip.at.": rr("1.1.1.1"),
            "change.hamip.at.": rr("9.9.9.9"),
            "new.hamip.at.": rr("4.4.4.4"),
        }
        client = FakeClient(current)
        to_remove, to_change = ZoneUpdater(client).sync(reference)

        self.assertEqual(set(to_remove), {"old.hamip.at.", "change.hamip.at."})
        self.assertEqual(set(to_change), {"change.hamip.at.", "new.hamip.at."})
        self.assertEqual(client.deleted, to_remove)
        self.assertEqual(client.replaced, to_change)
        self.assertTrue(client.serial_bumped)

    def test_no_changes_when_in_sync(self):
        records = {"keep.hamip.at.": rr("1.1.1.1")}
        client = FakeClient(dict(records))
        to_remove, to_change = ZoneUpdater(client).sync(dict(records))
        self.assertEqual(to_remove, {})
        self.assertEqual(to_change, {})
        self.assertTrue(client.serial_bumped)

    def test_empty_server_zone_raises(self):
        client = FakeClient({})
        with self.assertRaises(PowerDnsError):
            ZoneUpdater(client).sync({"new.hamip.at.": rr("4.4.4.4")})

    def test_missing_serial_raises(self):
        client = FakeClient({"keep.hamip.at.": rr("1.1.1.1")}, serial=None)
        with self.assertRaises(PowerDnsError):
            ZoneUpdater(client).sync({"keep.hamip.at.": rr("1.1.1.1")})


if __name__ == "__main__":
    unittest.main()
