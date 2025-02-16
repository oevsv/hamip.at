#!/usr/bin/python3

# Update hamip.at according to HamnetDB and local settings

# This code is released under the Apache License, Version 2.0.
# It was developed by Dietmar Zlabinger, oe3dzw

from datetime import datetime
import os
import sys
import yaml
from pprint import pprint

from hamnetdb_util import *
from powerdns_util import *


# https://doc.powerdns.com/authoritative/http-api/zone.html

api_endpoint = "https://dnsapi.netplanet.at/api"
API_KEY_ISP_LOCATION = "/etc/hamip/key.asc"
API_ENDPOINT_HAMNET = "http://127.0.0.1:8081/api"
API_KEY_HAMNET_LOCATION = "/etc/hamip/key_hamnet.asc"
HAMIP_AT = '.hamip.at.'

STATIC_ZONES_LOCATION = "/etc/hamip/static_records.yaml"

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


def get_static_zones(file_path):

    try:
        # Load dictionaries from YAML file
        with open(file_path, 'r') as file:
            data = yaml.safe_load(file)

        # validate yaml
        static_dict_isp = {}
        for k, v in data['isp'].items():
            # Explicitly map fields to ensure correct order
            static_dict_isp[k] = Resource_record(
                type=v['type'],
                content=v['content'],
                ttl=v['ttl']
            )

        static_dict_hamnet = {}
        for k, v in data['hamnet'].items():
            static_dict_hamnet[k] = Resource_record(
                type=v['type'],
                content=v['content'],
                ttl=v['ttl']
            )

        return static_dict_isp, static_dict_hamnet
    except Exception as e:
        # Catch exception if file operations failed (e.g. lack of permissions)
        print(f"Error loading static zones: {e}")
        return {}, {}  # Return empty dicts


def print_response(response):
    # make response more readable
    try:
        response_json = response.json()
        pprint(response_json)
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON response, error {e}")
        print(response.text)


def prepare_patch(task, delete, endpoint, api_key):
    chunk_size = 500

    # split into chunks
    items_list = list(task.items())
    for i in range(0, len(items_list), chunk_size):
        # Create a dictionary chunk
        chunk = dict(items_list[i:i + chunk_size])
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

        request_patch(endpoint, rrset_payload, 204, api_key)


def process_powerdns(endpoint, api_key, is_hamnet, static_zones_path):

    if DEBUG:
        print(f"is_hamnet = {is_hamnet}")

    zone_id = get_zones(endpoint, api_key)

    response = get_zone(endpoint, api_key)
    if not response.ok:
        print(f"Error fetching zone: {response.status_code}")
        print_response(response)
        sys.exit(1)
    # debug: print full zone response
    # print_response(response)
    data = response.json()

    # Retrieve the serial number
    serial = data.get('serial', None)
    print(f"Current serial: {serial}")

    if serial is None:
        print("No serial,failed")
        print_response(response)
        exit(1)

    # Retrieve the serial number
    edited_serial = data.get('edited_serial', None)
    if DEBUG:
        print(f"Current edited_serial: {edited_serial}")

    if edited_serial is None:
        print("No edited_serial,failed")
        print_response(response)
        exit(1)

    rrsets_dict_on_server = get_current_zone(zone_id, endpoint, api_key)
    # print("rrsets_dict_on_server")
    # print(rrsets_dict_on_server)

    # compare hamnetdb_dict_name_ip and hamnetdb_dict_aliases_cname with rrsets_dict_on_server

    # Dictionaries to hold removals and changes/additions
    to_remove = {}
    to_change = {}

    now = datetime.now()
    # Format the date and time, and include milliseconds
    formatted_date_time = now.strftime('%Y-%m-%d_%H-%M-%S') + f"_{now.microsecond // 1000:03d}"
    tag_dict = {
        "timestamp.hamip.at.": Resource_record(content="\"" + formatted_date_time + "\"", type="TXT", ttl=60),
    }

    static_dict_isp, static_dict_hamnet = get_static_zones(static_zones_path)
    # Default to empty dicts if loading failed
    static_dict_isp = static_dict_isp or {}
    static_dict_hamnet = static_dict_hamnet or {}

    if is_hamnet:
        reference_dict = (hamnetdb_dict | static_dict_hamnet | tag_dict)
    else:
        reference_dict = (hamnetdb_dict | static_dict_isp | tag_dict)
    # Process removal

    for key in rrsets_dict_on_server:
        if key not in reference_dict or rrsets_dict_on_server[key] != reference_dict[key]:
            if DEBUG:
                print("Mismatch:")
                print(f"on server: {rrsets_dict_on_server[key]}")
                print(f"reference: {reference_dict[key]}")
            to_remove[key] = rrsets_dict_on_server[key]

    print("Keys to be removed:", len(to_remove))
    if DEBUG:
        print(to_remove)

    prepare_patch(to_remove, True, endpoint, api_key)

    # Identify keys to change/add
    for key in reference_dict:
        # if new or changed
        key_not_on_server = key not in rrsets_dict_on_server
        # add if not there
        if key_not_on_server:
            to_change[key] = reference_dict[key]
        elif rrsets_dict_on_server[key] != reference_dict[key]:
            to_change[key] = reference_dict[key]

    print("Keys to be changed or added:", len(to_change))
    if DEBUG:
        print(to_change)

    prepare_patch(to_change, False, endpoint, api_key)

    enable_update_serial = True
    if enable_update_serial:
        update_serial(endpoint, api_key)

    if (len(to_remove) > 0 or len(to_change) > 0) and DEBUG:
        # get updated zone
        # get_zone(api_endpoint, api_key)
        print_response(response)


# main

# Initialize dictionaries
hamnetdb_dict = {}
get_hamnetdb_hosts(hamnetdb_dict, HAMIP_AT)

USE_DHCP = False

if USE_DHCP:
    dhcp_dict = {}
    get_hamnetdb_dhcp(dhcp_dict, hamnetdb_dict, HAMIP_AT)
    hamnetdb_dict = hamnetdb_dict | dhcp_dict

api_key_isp = read_auth_key(API_KEY_ISP_LOCATION)
if api_key_isp is None:
    print(f"Error: Key not found at", API_KEY_ISP_LOCATION, "or could not be read.")
    sys.exit(1)  # Exit with a non-zero status code

api_key_hamnet = read_auth_key(API_KEY_HAMNET_LOCATION)
if api_key_hamnet is None:
    print(f"Error: Key not found at", API_KEY_HAMNET_LOCATION, "or could not be read.")
    sys.exit(1)  # Exit with a non-zero status code

process_powerdns(api_endpoint, api_key_isp, False, STATIC_ZONES_LOCATION)
process_powerdns(API_ENDPOINT_HAMNET, api_key_hamnet, True, STATIC_ZONES_LOCATION)
