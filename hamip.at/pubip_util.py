# Prototype to include public IPs into Hamnet-DB records

# e.g. 185-236-164-044-inetip.wx.oe3gwu.hamip.at.
# shall become an A record with wx.oe3gwu.hamip.at. and 185.236.164.44

import re

def extract_ip_and_domain(input_string):
    # Define a regex pattern to match the specific format.
    # Each octet may be 1 to 3 digits (zero-padded or not).
    pattern = r"(\d{1,3})-(\d{1,3})-(\d{1,3})-(\d{1,3})-inetip\.([\w.-]+)"

    # Use re.search to find the first occurrence of the pattern
    match = re.search(pattern, input_string)

    if match:
        # Extract the IP parts and normalize them (strip leading zeros,
        # validate the 0-255 range) into a canonical dotted-quad address.
        ip_parts = [int(octet) for octet in match.groups()[:4]]
        if any(octet > 255 for octet in ip_parts):
            return None, None
        ip_address = '.'.join(str(octet) for octet in ip_parts)
        domain = match.group(5)
        return ip_address, domain
    else:
        return None, None

def main():
    # Example usage
    input_string = "185-236-164-044-inetip.wx.oe3gwu.hamip.at."
    ip, domain = extract_ip_and_domain(input_string)

    if ip and domain:
        print(f"Extracted IP: {ip}")
        print(f"Extracted Domain: {domain}")
    else:
        print("Pattern not found in the input string.")


# only execute main if not imported
if __name__ == "__main__":
    main()