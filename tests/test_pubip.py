"""Unit tests for hamipat.pubip.extract_ip_and_domain."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hamipat.pubip import extract_ip_and_domain  # noqa: E402


class TestExtractIpAndDomain(unittest.TestCase):

    def test_zero_padded_octets_are_normalized(self):
        ip, domain = extract_ip_and_domain("185-236-164-044-inetip.wx.oe3gwu.hamip.at.")
        self.assertEqual(ip, "185.236.164.44")
        self.assertEqual(domain, "wx.oe3gwu.hamip.at.")

    def test_non_padded_octets(self):
        ip, domain = extract_ip_and_domain("44-143-0-7-inetip.wx.oe3gwu.hamip.at.")
        self.assertEqual(ip, "44.143.0.7")
        self.assertEqual(domain, "wx.oe3gwu.hamip.at.")

    def test_octet_out_of_range_is_rejected(self):
        ip, domain = extract_ip_and_domain("999-1-1-1-inetip.x.hamip.at.")
        self.assertIsNone(ip)
        self.assertIsNone(domain)

    def test_no_match_returns_none(self):
        ip, domain = extract_ip_and_domain("not-an-inetip-name.hamip.at.")
        self.assertIsNone(ip)
        self.assertIsNone(domain)

    def test_all_zeros(self):
        ip, domain = extract_ip_and_domain("0-0-0-0-inetip.x.hamip.at.")
        self.assertEqual(ip, "0.0.0.0")
        self.assertEqual(domain, "x.hamip.at.")

    def test_max_valid_address(self):
        ip, domain = extract_ip_and_domain("255-255-255-255-inetip.x.hamip.at.")
        self.assertEqual(ip, "255.255.255.255")
        self.assertEqual(domain, "x.hamip.at.")


if __name__ == "__main__":
    unittest.main()
