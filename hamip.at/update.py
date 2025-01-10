#!/usr/bin/python3

import os, sys, requests, json
from pprint import pprint
from hamnetdb_util import *
from powerdns_util import *

# https://doc.powerdns.com/authoritative/http-api/zone.html

API_ENDPOINT_ISP = "https://dnsapi.netplanet.at/api"
API_KEY_ISP_LOCATION = "/etc/hamip/key.asc"
API_ENDPOINT_HAMNET = "http://127.0.0.1:8081/api"
API_KEY_HAMNET_LOCATION = "/etc/hamip/key_hamnet.asc"
HAMIP_AT = '.hamip.at.'

DEBUG = False


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


def print_response(response):
    # make response more readable
    try:
        response_json = response.json()
        pprint(response_json)
    except json.JSONDecodeError as e:
        print("Failed to decode JSON response")
        print(response.text)




def prepare_patch(task, delete, api_endpoint):
    CHUNK_SIZE = 500

    # split into chunks
    items_list = list(task.items())
    for i in range(0, len(items_list), CHUNK_SIZE):
        # Create a dictionary chunk
        chunk = dict(items_list[i:i + CHUNK_SIZE])
        # Process the current chunk

        # Convert the dictionary into the RRset JSON structure
        if delete:
            rrsets = [
                {
                    "name": f"{key}",
                    "type": value.type,
                    "changetype": "DELETE"
                }
                for key, value in chunk.items()
            ]
        else:
            rrsets = [
                {
                    "name": f"{key}",
                    "type": value.type,
                    "ttl": value.ttl,
                    "changetype": "REPLACE",
                    "records": [
                        {
                            "content": value.content,
                            "disabled": False
                        }
                    ]
                }
                for key, value in chunk.items()
            ]

        # Create the payload
        rrset_payload = {
            "rrsets": rrsets
        }

        request_patch(api_endpoint, rrset_payload, 204, api_key)



# main

# Initialize dictionaries
hamnetdb_dict = {}
get_hamnetdb_hosts(hamnetdb_dict, HAMIP_AT)

USE_DHCP = False

if USE_DHCP:
    dhcp_dict = {}
    get_hamnetdb_dhcp(dhcp_dict, hamnetdb_dict, HAMIP_AT)
    hamnetdb_dict = hamnetdb_dict | dhcp_dict

api_key = read_auth_key(API_KEY_ISP_LOCATION)
if api_key is None:
    print(f"Error: Key not found at", API_KEY_ISP_LOCATION, "or could not be read.")
    sys.exit(1)  # Exit with a non-zero status code
# print(api_key)

zone_id = get_zones(API_ENDPOINT_ISP, api_key)

response = get_zone(API_ENDPOINT_ISP, api_key)
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
if DEBUG:
    print(f"Current edited_serial: {edited_serial}")

if edited_serial == None:
    print("No edited_serial,failed")
    print_response(response)
    exit(1)

rrsets_dict_on_server = get_current_zone(zone_id, API_ENDPOINT_ISP, api_key)
# print("rrsets_dict_on_server")
# print(rrsets_dict_on_server)

# compare hamnetdb_dict_name_ip and hamnetdb_dict_aliases_cname with rrsets_dict_on_server

# Dictionaries to hold removals and changes/additions
to_remove = {}
to_change = {}

static_dict = {
    "*": Resource_record(content="89.185.96.125", type="A", ttl=600),
    "hamip.at.": Resource_record(content="89.185.96.125", type="A", ttl=600)
}

# Process removal

for key in rrsets_dict_on_server:
    if (key not in hamnetdb_dict
            and key not in static_dict):
        to_remove[key] = rrsets_dict_on_server[key]

print("Keys to be removed:", len(to_remove))
# print(to_remove)

prepare_patch(to_remove, True, API_ENDPOINT_ISP)

# Identify keys to change/add
for key in hamnetdb_dict:
    # if new or changed
    key_not_on_server = key not in rrsets_dict_on_server
    # add if not there
    if key_not_on_server:
        to_change[key] = hamnetdb_dict[key]
    elif rrsets_dict_on_server[key] != hamnetdb_dict[key]:
        to_change[key] = hamnetdb_dict[key]

print("Keys to be changed or added:", len(to_change))

prepare_patch(to_change, False, API_ENDPOINT_ISP)

ENABLE_UPDATE_SERIAL = True
if ENABLE_UPDATE_SERIAL:
    update_serial(API_ENDPOINT_ISP, api_key)

if len(to_remove) > 0 or len(to_change) > 0 and DEBUG:
    # getupdated zone
    get_zone(API_ENDPOINT_ISP, api_key)
    print_response(response)
