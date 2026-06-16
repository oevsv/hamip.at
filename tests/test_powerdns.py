"""Unit tests for PowerDnsClient parsing and patch generation."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hamipat.powerdns import PowerDnsClient  # noqa: E402
from hamipat.records import ResourceRecord  # noqa: E402


class FakeResponse:
    def __init__(self, status_code=204):
        self.status_code = status_code
        self.text = ""


class RecordingSession:
    """Captures PATCH payloads so chunking/format can be asserted."""

    def __init__(self):
        self.patches = []

    def patch(self, url, headers=None, data=None):
        self.patches.append(json.loads(data))
        return FakeResponse(204)


class TestParseRecords(unittest.TestCase):

    def test_only_managed_types_are_kept(self):
        zone = {"rrsets": [
            {"name": "a.hamip.at.", "type": "A", "ttl": 600,
             "records": [{"content": "44.1.1.1"}]},
            {"name": "hamip.at.", "type": "SOA", "ttl": 3600,
             "records": [{"content": "ns. hostmaster. 1 1 1 1 1"}]},
            {"name": "c.hamip.at.", "type": "CNAME", "ttl": 600,
             "records": [{"content": "a.hamip.at."}]},
        ]}
        records = PowerDnsClient.parse_records(zone)
        self.assertEqual(set(records), {"a.hamip.at.", "c.hamip.at."})
        self.assertEqual(records["a.hamip.at."],
                         ResourceRecord("A", "44.1.1.1", 600))


class TestPatchGeneration(unittest.TestCase):

    def _client(self, session, chunk_size=500):
        return PowerDnsClient("http://x/api", "key", session=session, chunk_size=chunk_size)

    def test_replace_payload_format(self):
        session = RecordingSession()
        self._client(session).replace_records(
            {"a.hamip.at.": ResourceRecord("A", "44.1.1.1", 600)})
        rrset = session.patches[0]["rrsets"][0]
        self.assertEqual(rrset["changetype"], "REPLACE")
        self.assertEqual(rrset["ttl"], 600)
        self.assertEqual(rrset["records"], [{"content": "44.1.1.1", "disabled": False}])

    def test_delete_payload_format(self):
        session = RecordingSession()
        self._client(session).delete_records(
            {"a.hamip.at.": ResourceRecord("A", "44.1.1.1", 600)})
        rrset = session.patches[0]["rrsets"][0]
        self.assertEqual(rrset["changetype"], "DELETE")
        self.assertNotIn("records", rrset)

    def test_chunking(self):
        session = RecordingSession()
        records = {f"h{i}.hamip.at.": ResourceRecord("A", f"44.0.0.{i}", 600)
                   for i in range(5)}
        self._client(session, chunk_size=2).replace_records(records)
        self.assertEqual([len(p["rrsets"]) for p in session.patches], [2, 2, 1])

    def test_empty_records_send_no_request(self):
        session = RecordingSession()
        self._client(session).replace_records({})
        self.assertEqual(session.patches, [])


if __name__ == "__main__":
    unittest.main()
