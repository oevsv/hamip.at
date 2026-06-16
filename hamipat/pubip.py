"""Parse a public IP embedded in a HamnetDB name (prototype).

A name of the form ``185-236-164-044-inetip.wx.oe3gwu.hamip.at.`` encodes the
public IP ``185.236.164.44`` for the domain ``wx.oe3gwu.hamip.at.``.
"""
import re

# Each octet may be 1 to 3 digits (zero-padded or not).
_INETIP_RE = re.compile(r"(\d{1,3})-(\d{1,3})-(\d{1,3})-(\d{1,3})-inetip\.([\w.-]+)")


def extract_ip_and_domain(input_string):
    """Return ``(ip, domain)`` parsed from ``input_string``, or ``(None, None)``.

    Octets are normalized (leading zeros stripped) and range-checked (0-255).
    """
    match = _INETIP_RE.search(input_string)
    if not match:
        return None, None

    octets = [int(part) for part in match.groups()[:4]]
    if any(octet > 255 for octet in octets):
        return None, None

    ip_address = ".".join(str(octet) for octet in octets)
    domain = match.group(5)
    return ip_address, domain


def main():
    example = "185-236-164-044-inetip.wx.oe3gwu.hamip.at."
    ip, domain = extract_ip_and_domain(example)
    if ip and domain:
        print(f"Extracted IP: {ip}")
        print(f"Extracted Domain: {domain}")
    else:
        print("Pattern not found in the input string.")


if __name__ == "__main__":
    main()
