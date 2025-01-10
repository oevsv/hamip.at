#!/usr/bin/python3

import os, sys, requests, json
from pprint import pprint
from collections import namedtuple
from hamnetdb_util import get_hamnetdb_hosts, get_hamnetdb_dhcp

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


def request_patch(endpoint, headers, payload, status_code):
    # delete:
    # {'rrsets': [{'name': 'testing2.oe0any.hamip.at.', 'type': 'A', 'changetype': 'DELETE'}]}

    # change:
    # {'rrsets': [{'name': 'testing2.oe0any.hamip.at.', 'type': 'A', 'ttl': 600, 'changetype': 'REPLACE',
    #            'records': [{'content': '44.143.0.7',     'disabled': False}]}]}
    # {'rrsets': [{'name': 'hr.oe5xoo.hamip.at.',       'type': 'A', 'ttl': 600, 'changetype': 'REPLACE',
    #            'records': [{'content': '44.143.108.254', 'disabled': False}]}

    if DEBUG:
        print(f"\nPatch payload: {payload}")
    response = requests.patch(endpoint, headers=headers, data=json.dumps(payload))
    # Check the response
    if response.status_code != status_code:
        print(f"Failed to patch. Status code: {response.status_code}")
        print("Response:", response.text)
        print("Payload:", payload)
        raise NameError("Failed to patch.")
    return response



Resource_record = namedtuple("Resource_record", ["type", "content", "ttl"])

def get_current_zone(zone_id, endpoint, headers):
    # Sample response:
    # 'tun-oe8xvr.ir3uda.hamip.at.': Resource_record(type='A', content='44.134.125.249', ttl=600)

    # current zone
    API_ENDPOINT = API_ENDPOINT_ISP + "/v1/servers/localhost/zones/hamip.at"
    response = requests.get(API_ENDPOINT, headers=headers)

    # Sample record
    #               {'comments': [],
    #              'name': 'test.hamip.at.',
    #              'records': [{'content': '192.168.49.0', 'disabled': False}],
    #              'ttl': 3600,
    #              'type': 'A'},

    # Parse the JSON data
    data = response.json()
    zone_data = data.get(zone_id, {})

    # Retrieve only the relevant information from rrsets
    rrsets_dict_on_server = {}
    for rrset in data.get('rrsets', []):
        name = rrset.get('name')
        type = rrset.get('type')
        for record in rrset.get('records', []):
            # Include specific record types
            if type == 'A' or type == 'CNAME' or type == 'TXT':
                content = record.get('content')
                ttl = rrset.get('ttl')
                rrsets_dict_on_server[name] = Resource_record(content=content, type=type, ttl=ttl)

    print(f"Rrsets on server: {len(rrsets_dict_on_server)}")

    if len(rrsets_dict_on_server) == 0:
        print("failed to get rr_sets from server")
        exit(-1)
    return (rrsets_dict_on_server)

def update_serial():
    # Update serial
    payload = {
        "soa_edit_api": "INCREASE",
        "kind": "Native",
        "soa_edit": "INCREASE"
    }

    API_ENDPOINT = API_ENDPOINT_ISP + "/v1/servers/localhost/zones/hamip.at"
    response = requests.put(API_ENDPOINT, headers=headers, data=json.dumps(payload))

    # Check the response status
    if response.status_code == 204:
        print("Zone updated successfully.")
    else:
        print(f"Failed to update zone. Status code: {response.status_code}")
        print("Response:", response.text)


def prepare_patch(task, delete, api_endpoint):

    CHUNK_SIZE = 500

    # split into chunks
    items_list = list(task.items())
    for i in range(0, len(items_list),CHUNK_SIZE):
        # Create a dictionary chunk
        chunk = dict(items_list[i:i + CHUNK_SIZE])
        # Process the current chunk


        # Convert the dictionary into the RRset JSON structure
        if  delete:
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

        # update header, here we need to specify the content type
        headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }

        ENDPOINT = api_endpoint + "/v1/servers/localhost/zones/hamip.at"
        request_patch(ENDPOINT, headers, rrset_payload, 204)


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

# put the key into a request header
headers = {
    'X-API-Key': api_key
}

zone_id = None

# Check if the server is alive
try:
    API_ENDPOINT: str = API_ENDPOINT_ISP + "/v1/servers/localhost/zones"
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
API_ENDPOINT = API_ENDPOINT_ISP + "/v1/servers/localhost/zones/hamip.at"
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
if DEBUG:
    print(f"Current edited_serial: {edited_serial}")

if edited_serial == None:
    print("No edited_serial,failed")
    print_response(response)
    exit(1)

rrsets_dict_on_server = get_current_zone(zone_id, API_ENDPOINT, headers)
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
    if (key_not_on_server):
        to_change[key] = hamnetdb_dict[key]
    elif rrsets_dict_on_server[key] != hamnetdb_dict[key]:
        to_change[key] = hamnetdb_dict[key]

print("Keys to be changed or added:", len(to_change))

prepare_patch(to_change, False, API_ENDPOINT_ISP)

# serial is updated automatically in some magic. this should enable the setting, it needs
# to be done only once, not at every update
UPDATE_SERIAL = True



if len(to_remove) > 0 or len(to_change) > 0:
    # getupdated zone
    response = requests.get(API_ENDPOINT, headers=headers)
    if DEBUG:
        print_response(response)
