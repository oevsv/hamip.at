#!/usr/bin/python3

# required to read files
import os
# required for exit value
import sys

# needed for API request
import requests

import json
# make json readable
from pprint import pprint

# Libs:
# https://pypi.org/project/python-powerdns/
# import powerdns

# https://doc.powerdns.com/authoritative/http-api/zone.html

API_ENDPOINT_BASE = "https://dnsapi.netplanet.at/api"
API_KEY_LOCATION = "/etc/hamip/key.asc"


# import authkey from /etc/hamip/key.asc
def read_auth_key(file_path):
    """
    Reads a key from a file and returns it as a string.
    If the file cannot be read, returns None.

    :param file_path: Path to the key file (e.g., '/etc/hamip/key.asc').
    :return: The key as a string or None if the file can't be read.
    """
    try:
        # Check if the file exists and is readable
        if not os.path.isfile(file_path):
            print("debug, file does not exist")
            return None

        # Open the file and read its contents
        with open(file_path, 'r') as file:
            key = file.read().strip()  # Strip to remove leading/trailing whitespace

        # Return None if the file is empty
        if not key:
            return None

        return key
    except Exception as e:
        # Catch exception if file operations failed (e.g. lack of permissions)
        print(f"debug, an error occurred: {e}")
        return None


api_key = read_auth_key(API_KEY_LOCATION)
if api_key is None:
    print(f"Error: Key not found at", API_KEY_LOCATION, "or could not be read.")
    sys.exit(1)  # Exit with a non-zero status code
print(api_key)

# Make a request to the API
headers = {
    'X-API-Key': api_key
}

API_ENDPOINT = API_ENDPOINT_BASE+"/v1/servers/localhost/zones/hamip.at"

response = requests.get(API_ENDPOINT, headers=headers)

# print raw response
# print(response.text)

# make response more readable
try:
    response_json = response.json()
    pprint(response_json)
except json.JSONDecodeError as e:
    print("Failed to decode JSON response")
    print(response.text)

