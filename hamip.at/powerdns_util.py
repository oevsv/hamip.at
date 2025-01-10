import json
from collections import namedtuple

import requests

DEBUG = False

def get_zone(endpoint,api_key):
    # put the key into a request header
    headers = {
        'X-API-Key': api_key
    }

    ENDPOINT = endpoint + "/v1/servers/localhost/zones/hamip.at"
    response = requests.get(ENDPOINT, headers=headers)
    return response


def request_patch(api_endpoint, payload, status_code, api_key):

    # update header, here we need to specify the content type
    headers = {
        'X-API-Key': api_key,
        'Content-Type': 'application/json'
    }

    full_end_point = api_endpoint + "/v1/servers/localhost/zones/hamip.at"

    # delete:
    # {'rrsets': [{'name': 'testing2.oe0any.hamip.at.', 'type': 'A', 'changetype': 'DELETE'}]}

    # change:
    # {'rrsets': [{'name': 'testing2.oe0any.hamip.at.', 'type': 'A', 'ttl': 600, 'changetype': 'REPLACE',
    #            'records': [{'content': '44.143.0.7',     'disabled': False}]}]}
    # {'rrsets': [{'name': 'hr.oe5xoo.hamip.at.',       'type': 'A', 'ttl': 600, 'changetype': 'REPLACE',
    #            'records': [{'content': '44.143.108.254', 'disabled': False}]}

    if DEBUG:
        print(f"\nPatch payload: {payload}")
    response = requests.patch(full_end_point, headers=headers, data=json.dumps(payload))
    # Check the response
    if response.status_code != status_code:
        print(f"Failed to patch. Status code: {response.status_code}")
        print("Response:", response.text)
        print("Payload:", payload)
        raise NameError("Failed to patch.")
    return response


Resource_record = namedtuple("Resource_record", ["type", "content", "ttl"])


def get_zones(api_endpoint,api_key):
    # put the key into a request header
    headers = {
        'X-API-Key': api_key
    }

    zone_id = None
    # Check if the server is alive
    try:
        full_end_point: str = api_endpoint + "/v1/servers/localhost/zones"
        response = requests.get(full_end_point, headers=headers)
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
        return zone_id

    except json.JSONDecodeError:
        print("Failed to decode JSON response")
        print(response.text)


def get_current_zone(zone_id, api_endpoint,api_key):
    # Sample response:
    # 'tun-oe8xvr.ir3uda.hamip.at.': Resource_record(type='A', content='44.134.125.249', ttl=600)

    # put the key into a request header
    headers = {
        'X-API-Key': api_key
    }

    # current zone
    full_end_point = api_endpoint + "/v1/servers/localhost/zones/hamip.at"
    response = requests.get(full_end_point, headers=headers)

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

    print(f"Rrsets on {api_endpoint}: {len(rrsets_dict_on_server)}")

    if len(rrsets_dict_on_server) == 0:
        print("failed to get rr_sets from server")
        exit(-1)
    return (rrsets_dict_on_server)


def update_serial(api_endpoint,api_key):

    # put the key into a request header
    headers = {
        'X-API-Key': api_key
    }

    # Update serial
    payload = {
        "soa_edit_api": "INCREASE",
        "kind": "Native",
        "soa_edit": "INCREASE"
    }

    full_end_point = api_endpoint + "/v1/servers/localhost/zones/hamip.at"
    response = requests.put(full_end_point, headers=headers, data=json.dumps(payload))

    # Check the response status
    if response.status_code == 204:
        print("Zone updated successfully.")
    else:
        print(f"Failed to update zone. Status code: {response.status_code}")
        print("Response:", response.text)
