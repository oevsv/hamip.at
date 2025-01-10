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

# to parse IPs
import ipaddress

from collections import namedtuple

import time

# https://doc.powerdns.com/authoritative/http-api/zone.html

API_ENDPOINT_BASE = "https://dnsapi.netplanet.at/api"
API_KEY_LOCATION = "/etc/hamip/key.asc"
HAMIP_AT = '.hamip.at.'


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
    return f"test{random.randint(10 ** 31, 10 ** 32 - 1)}.hamip.at"


# Function to generate a random IP address in the 192.168.x.x range
def generate_random_ip():
    return f"192.168.{random.randint(0, 255)}.{random.randint(0, 255)}"


# Create the rrset_dict with n random entries
rrset_dict = {
    generate_random_subdomain(): generate_random_ip()
    for _ in range(10)
}


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

    print(f"\nPatch payload: {payload}")
    response = requests.patch(endpoint, headers=headers, data=json.dumps(payload))
    # Check the response
    if response.status_code != status_code:
        print(f"Failed to patch. Status code: {response.status_code}")
        print("Response:", response.text)
        print("Payload:", payload)
        raise NameError(f"Failed to patch. Status code: {response.status_code}")
    return response


def get_hamnetdb_dhcp(dhcp_dict):
    # Endpoint for HamnetDB
    HAMNETDB_ENDPOINT = "https://hamnetdb.net/csv.cgi?tab=subnet&json=1"

    # {
    #     "edited": "2021-06-06 16:10:23",
    #     "id": 6041,
    #     "ip": "44.143.53.32/28",
    #     "deleted": 0,
    #     "maintainer": "",
    #     "editor": "oe3dzw",
    #     "as_num": 0,
    #     "rw_maint": 0,
    #     "typ": "User-Network",
    #     "version": 3,
    #     "end_ip": 747582768,
    #     "as_parent": 4223230011,
    #     "dhcp_range": "35-46",
    #     "begin_ip": 747582752,
    #     "radioparam": "2422MHz@10MHz BW Omni",
    #     "no_check": 0,
    #     "comment": ""
    # },

    try:
        response = requests.get(HAMNETDB_ENDPOINT)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from HamnetDB: {e}")
        return

    try:
        data = response.json()
        print("HamnetDB-size:", len(data))

        # Iterate over each subnet entry
        for entry in data:
            # Skip deleted entries
            if entry.get("deleted") != 0:
                continue

            # Convert begin_ip to an IPv4 address
            base_ip = str(ipaddress.IPv4Address(entry['begin_ip']))

            # Parse the dhcp_range
            dhcp_range = entry.get('dhcp_range', '')
            if not dhcp_range:
                continue

            range_start, range_end = map(int, dhcp_range.split('-'))

            # dhcp-44-143-60-39.oe3xnr - implied by consistency check of
            # Hamnetdb "Site-Network is empty (no host address found)"

            # TODO: find first host, use that host as hostname for the dhcp-range (assume match)

            # Convert the CIDR to an IP network and compile the list of IPs
            all_ips = []
            cidr = entry.get('ip', '')
            print(cidr)
            if cidr:
                try:
                    network = ipaddress.ip_network(cidr, strict=False)
                    ips = [str(ip) for ip in network.hosts()]
                    all_ips.extend(ips)
                except ValueError as e:
                    print(f"Error processing CIDR {cidr}: {e}")
                    continue

            print(all_ips)

            # TODO: Now lookup hosts to find the name of the site
            # TODO: Filter by oe-hosts

            # Generate the dictionary entries
            for i in range(range_start, range_end + 1):
                octets = base_ip.split('.')
                octets[3] = str(i)  # Replace the last octet with each number in the range
                new_ip = '.'.join(octets)

                name = "todo"
                dhcp_dict[f"dhcp-{new_ip.replace('.', '-')}.{name}"] = new_ip

    except (json.JSONDecodeError, ValueError) as e:
        print("Failed to decode JSON data or parse ranges:", e)

    # Print the resulting dictionary
    # print(dhcp_dict)


Resource_record = namedtuple("Resource_record", ["type", "content", "ttl"])


def get_hamnetdb_hosts(hamnet_dict):
    # Endpoint for HamnetDB
    HAMNETDB_ENDPOINT = "https://hamnetdb.net/csv.cgi?tab=host&json=1"

    # Example response:
    # {
    #     "ip": "44.143.60.66",
    #     "edited": "2023-05-13 09:55:56",
    #     "comment": "Main web server OE3XNR, iGate APRS 144.800 MHz",
    #     "routing": 0,
    #     "monitor": 1,
    #     "mac": "",
    #     "radioparam": "",
    #     "no_ping": 0,
    #     "rawip": 747584578,
    #     "site": "oe3xnr",
    #     "id": 14448,
    #     "aliases": "www.oe3xnr,aprs.oe3xnr,index.oe3xnr,web.oe3xzr,admin.oe3xnr,shack.oe3xnr,aprs.oe3xnr,cam.oe3xnr,cam.oe3xhr,search.oe3xnr,file.oe3xnr,search.oe3xnr",
    #     "maintainer": "",
    #     "rw_maint": 0,
    #     "name": "web.oe3xnr",
    #     "typ": "Service",
    #     "version": 16,
    #     "editor": "oe3dzw",
    #     "deleted": 0
    # },

    try:
        response = requests.get(HAMNETDB_ENDPOINT)
        response.raise_for_status()  # Raise an exception for HTTP errors
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from HamnetDB: {e}")
        return

    try:
        entries = response.json()
        print("HamnetDB-size:", len(entries))
        # filter entries, thus massive speedup on later processing
        entries = [entry for entry in entries if entry.get('site', '').startswith('oe')]
        print("HamnetDB-size, OE filtered:", len(entries))

        site_list = []
        # Iterate over each entry
        for entry in entries:
            site = entry.get("site")
            if site not in site_list:
                site_list.append(site)
            host_name = entry.get("name")+HAMIP_AT

            ip = entry.get("ip")
            deleted = entry.get("deleted")
            if deleted == 0:
                # Add name and IP to name_ip_dict

                if host_name and ip and host_name not in hamnet_dict:
                    hamnet_dict[host_name] = Resource_record(content=ip, type="A", ttl=600)
                    if host_name.endswith('.oe0any.hamip.at.'):
                        special_host = host_name.replace(".oe0any", "")
                        if special_host not in hamnet_dict:
                            hamnet_dict[special_host] = Resource_record(content=ip, type="A", ttl=600)

                # Add aliases and IP to aliases_ip_dict
                aliases = entry.get("aliases", "")
                if aliases:
                    for alias in aliases.split(','):
                        alias_host_name = alias.strip() + HAMIP_AT
                        if alias_host_name != host_name and alias_host_name not in hamnet_dict:
                            hamnet_dict[alias_host_name] = Resource_record(content=host_name, type="CNAME", ttl=600)
                            #if alias_host_name.endswith('.oe0any.hamip.at.'):
                            #    special_host = host_name.replace(".oe0any", "")
                            #    if special_host not in hamnet_dict:
                            #        hamnet_dict[special_host] = Resource_record(content=host_name, type="CNAME", ttl=600)
                            # news-global.oe1xqu.hamip.at => news.hamip.at
                            # print(f"got alias {alias_host_name} with site {site}")
                            if alias_host_name.endswith('-global.'+site+'.hamip.at.'):
                                # print("found")
                                special_host = alias_host_name.replace('-global.'+site+'.hamip.at.', "") + HAMIP_AT
                                # print(f"special host {special_host}")
                                if special_host not in hamnet_dict:
                                    hamnet_dict[special_host] = Resource_record(content=host_name, type="CNAME", ttl=600)

        start_time = time.time()

        site_list.sort()
        for site in site_list:
            site_domain = site + HAMIP_AT
            if site_domain not in hamnetdb_dict:
                if "www." + site_domain in hamnet_dict and hamnet_dict["www." + site_domain].type == 'A':
                    hamnet_dict[site_domain] = Resource_record(content="www." + site_domain, type="CNAME", ttl=600)
                elif "web." + site_domain in hamnet_dict and hamnet_dict["web." + site_domain].type == 'A':
                    hamnet_dict[site_domain] = Resource_record(content="web." + site_domain, type="CNAME", ttl=600)
                elif "bb." + site_domain in hamnet_dict and hamnet_dict["bb." + site_domain].type == 'A':
                    hamnet_dict[site_domain] = Resource_record(content="bb." + site_domain, type="CNAME", ttl=600)
                elif "router." + site_domain in hamnet_dict and hamnet_dict["router." + site_domain].type == 'A':
                    hamnet_dict[site_domain] = Resource_record(content="router." + site_domain, type="CNAME", ttl=600)
                else:
                    # fallback to any other prefix (e.g. bb.<site>)
                    for name, record in hamnet_dict.items():
                        if name.endswith("." + site_domain):
                            hamnet_dict[site_domain] = Resource_record(content=name, type="CNAME", ttl=600)
                            break

        end_time = time.time()

        # Calculate the elapsed time
        elapsed_time = end_time - start_time

        # Display the time taken
        print(f"Function execution time: {elapsed_time:.6f} seconds")

        # Show the results
        print(f"Dictionary: {len(hamnet_dict)}")
        # print(json.dumps(hamnet_dict, indent=2))

    except json.JSONDecodeError:
        print("Failed to decode JSON data")


def get_current_zone(zone_id, endpoint, headers):
    # Sample response:
    # 'tun-oe8xvr.ir3uda.hamip.at.': Resource_record(type='A', content='44.134.125.249', ttl=600)

    # current zone
    API_ENDPOINT = API_ENDPOINT_BASE + "/v1/servers/localhost/zones/hamip.at"
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


# Initialize dictionaries
hamnetdb_dict = {}
get_hamnetdb_hosts(hamnetdb_dict)

dhcp_dict = {}
# get_hamnetdb_dhcp(dhcp_dict)


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
API_ENDPOINT = API_ENDPOINT_BASE + "/v1/servers/localhost/zones/hamip.at"
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

# Identify keys to remove (present in old_dict but not in new_dict)
# intruduce limit to avoid too complex requests
DELETE_MAX_COUNT = 10000
delete_count = 0
for key in rrsets_dict_on_server:
    if (key not in hamnetdb_dict
            and key not in static_dict):
        delete_count = delete_count + 1
        if delete_count <= DELETE_MAX_COUNT:
            to_remove[key] = rrsets_dict_on_server[key]

print("Keys to be removed:", len(to_remove))
# print(to_remove)

REPLACE_MAX_COUNT = 10000
replace_count = 0
# Identify keys to change/add
for key in hamnetdb_dict:
    # if new or changed
    key_not_on_server = key not in rrsets_dict_on_server
    # add if not there
    if (key_not_on_server):
        replace_count = replace_count + 1;
        if replace_count <= REPLACE_MAX_COUNT:
            to_change[key] = hamnetdb_dict[key]
    elif rrsets_dict_on_server[key] != hamnetdb_dict[key]:
        replace_count = replace_count + 1;
        if replace_count <= REPLACE_MAX_COUNT:
            to_change[key] = hamnetdb_dict[key]

print("\nKeys to be changed or added:", len(to_change))
# print(to_change)

# Convert the dictionary into the RRset JSON structure
rrsets_remove = [
    {
        "name": f"{key}",
        "type": value.type,
        "changetype": "DELETE"
    }
    for key, value in to_remove.items()
]

rrsets_change = [
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
    for key, value in to_change.items()
]

# Create the payload
rrset_remove_payload = {
    "rrsets": rrsets_remove
}
# Create the payload
rrset_change_payload = {
    "rrsets": rrsets_change
}

# update header, here we need to specify the content type
headers = {
    'X-API-Key': api_key,
    'Content-Type': 'application/json'
}

API_ENDPOINT = API_ENDPOINT_BASE + "/v1/servers/localhost/zones/hamip.at"
if len(to_remove) > 0:
    request_patch(API_ENDPOINT, headers, rrset_remove_payload, 204)
if len(to_change) > 0:
    request_patch(API_ENDPOINT, headers, rrset_change_payload, 204)

# serial is updated automatically in some magic. this should enable the setting, it needs
# to be done only once, not at every update
UPDATE_SERIAL = False

if UPDATE_SERIAL:
    # Update serial
    payload = {
        "soa_edit_api": "INCREASE",
        "kind": "Native",
        "soa_edit": "INCREASE"
    }

    API_ENDPOINT = API_ENDPOINT_BASE + "/v1/servers/localhost/zones/hamip.at"
    response = requests.put(API_ENDPOINT, headers=headers, data=json.dumps(payload))

    # Check the response status
    if response.status_code == 204:
        print("Zone updated successfully.")
    else:
        print(f"Failed to update zone. Status code: {response.status_code}")
        print("Response:", response.text)

if len(to_remove) > 0 or len(to_change) > 0:
    # getupdated zone
    response = requests.get(API_ENDPOINT, headers=headers)
    print_response(response)
