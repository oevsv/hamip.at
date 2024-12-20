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

# to generate debugging/testing data
import random

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


# Function to generate random domains including a random 32-digit number
def generate_random_subdomain():
    return f"test{random.randint(10**31, 10**32 - 1)}.hamip.at"

# Function to generate a random IP address in the 192.168.x.x range
def generate_random_ip():
    return f"192.168.{random.randint(0, 255)}.{random.randint(0, 255)}"

# Create the rrset_dict with n random entries
rrset_dict = {
    generate_random_subdomain(): generate_random_ip()
    for _ in range(1)
}

def print_response(response):
    # make response more readable
    try:
        response_json = response.json()
        pprint(response_json)
    except json.JSONDecodeError as e:
        print("Failed to decode JSON response")
        print(response.text)

api_key = read_auth_key(API_KEY_LOCATION)
if api_key is None:
    print(f"Error: Key not found at", API_KEY_LOCATION, "or could not be read.")
    sys.exit(1)  # Exit with a non-zero status code
# print(api_key)

# put the key into a request header
headers = {
    'X-API-Key': api_key
}

zone_id = None

# Check if the server is alive
try:
    API_ENDPOINT: str = API_ENDPOINT_BASE + "/v1/servers/localhost/zones"
    response = requests.get(API_ENDPOINT, headers=headers)
    response_json = response.json()

    # check if the 'url' key matches the expected value
    expected_url = '/api/v1/servers/localhost/zones/hamip.at.'

    # Iterate over all keys and look for the 'url' field
    found_url = False
    for key, value in response_json.items():
        # Try to get the 'url' from the sub-dictionary
        url = value.get('url')
        if url and url == expected_url:
            zone_id = key
            found_url = True

    if found_url:
        print(f"Zone ID: {zone_id}")
    else:
        print(f"Key '{expected_url}' not found in the response")


except json.JSONDecodeError:
    print("Failed to decode JSON response")
    print(response.text)


# request to load data into rrset and get serial

# getupdated zone
API_ENDPOINT = API_ENDPOINT_BASE+"/v1/servers/localhost/zones/hamip.at"
response = requests.get(API_ENDPOINT, headers=headers)

data = response.json()

# Retrieve the serial number
serial = data.get('serial', None)
print(f"Current serial: {serial}")

if serial == None:
    print("No serial,failed")
    print_response(response)
    exit(-1)

# Retrieve the serial number
edited_serial = data.get('edited_serial', None)
print(f"Current edited_serial: {edited_serial}")

if edited_serial == None:
    print("No edited_serial,failed")
    print_response(response)
    exit(-1)

# current zone
API_ENDPOINT = API_ENDPOINT_BASE+"/v1/servers/localhost/zones/hamip.at"
response = requests.get(API_ENDPOINT, headers=headers)

# Parse the JSON data
data = response.json()
zone_data = data.get(zone_id, {})

# Retrieve only the relevant information from rrsets
rrsets_dict_on_server = {}
for rrset in data.get('rrsets', []):
    name = rrset.get('name')
    for record in rrset.get('records', []):
        # Only include 'A' type records
        if rrset.get('type') == 'A':
            ip_address = record.get('content')
            rrsets_dict_on_server[name] = ip_address

print(f"Rrsets on server: {len(rrsets_dict_on_server)}")

if len(rrsets_dict_on_server)==0:
    print("failed to get rr_sets from server")
    exit(-1)

# Filtering the rrsets based on "test" prefix
filtered_rrsets_dict = {}
for name, ip_address in rrsets_dict_on_server.items():
    if name.startswith("test"):
        filtered_rrsets_dict[name] = ip_address

print(f"Filtered rrsets size: {len(filtered_rrsets_dict)}")

if len(filtered_rrsets_dict) == 0:
    print("No RRsets starting with 'test' found.")
    exit(-1)

# Convert the dictionary into the RRset JSON structure
rrsets = [
    {
        "name": f"{name}",
        "type": "A",
        "changetype": "DELETE"
    }
    for name, ip in filtered_rrsets_dict.items()
]


# Create the payload
rrset_payload = {
    "rrsets": rrsets
}



# update header, here we need to specify the content type
headers = {
    'X-API-Key': api_key,
    'Content-Type': 'application/json'
}

API_ENDPOINT = API_ENDPOINT_BASE+"/v1/servers/localhost/zones/hamip.at"

response = requests.patch(API_ENDPOINT, headers=headers, data=json.dumps(rrset_payload))


# Check the response
if response.status_code == 204:
    print("RRsets patched/deleted successfully.")
else:
   print(f"Failed to patch/delete RRsets. Status code: {response.status_code}")
   print("Response:", response.text)
   print("Payload:", rrset_payload)
   exit(-1)


# Update serial

# Set SOA-EDIT to INCREASE
payload = {
        "name": "hamip.at.",
        "soa_edit_api": "INCREASE",
        "kind": "Native"

    }



API_ENDPOINT = API_ENDPOINT_BASE+"/v1/servers/localhost/zones/hamip.at"
response = requests.put(API_ENDPOINT, headers=headers, data=json.dumps(payload))

# Check the response status
if response.status_code == 204:
    print("Zone updated successfully.")
else:
    print(f"Failed to update zone. Status code: {response.status_code}")
    print("Response:", response.text)

# getupdated zone
response = requests.get(API_ENDPOINT, headers=headers)
print_response(response)
