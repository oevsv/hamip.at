# hamnetdb_util.py
import ipaddress
import json
import time
from collections import namedtuple

import requests

# Utilities requesting data from the Hamnet-DB


Resource_record = namedtuple("Resource_record", ["type", "content", "ttl"])


def get_hamnetdb_hosts(hamnet_dict, hamip_at):
    # Endpoint for HamnetDB
    hamnetdb_endpoint = "https://hamnetdb.net/csv.cgi?tab=host&json=1"

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
    #     "aliases": "www.oe3xnr,aprs.oe3xnr,index.oe3xnr,web.oe3xzr,admin.oe3xnr,shack.oe3xnr,aprs.oe3xnr,cam.oe3xnr,
    #         cam.oe3xhr,search.oe3xnr,file.oe3xnr,search.oe3xnr",
    #     "maintainer": "",
    #     "rw_maint": 0,
    #     "name": "web.oe3xnr",
    #     "typ": "Service",
    #     "version": 16,
    #     "editor": "oe3dzw",
    #     "deleted": 0
    # },

    DEBUG = False

    try:
        response = requests.get(hamnetdb_endpoint)
        response.raise_for_status()  # Raise an exception for HTTP errors
    except requests.exceptions.RequestException as e:
        if DEBUG:
            print(f"Error fetching data from HamnetDB: {e}")
        return

    try:
        entries = response.json()
        if DEBUG:
            print("HamnetDB-size:", len(entries))
        # filter entries, thus massive speedup on later processing
        entries = [entry for entry in entries if entry.get('site', '').startswith('oe')]
        if DEBUG:
            print("HamnetDB-size, OE filtered:", len(entries))

        site_list = []
        # Iterate over each entry
        for entry in entries:
            site = entry.get("site")
            if site not in site_list:
                site_list.append(site)
            host_name = entry.get("name")+hamip_at
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
                        alias_host_name = alias.strip() + hamip_at
                        if alias_host_name != host_name and alias_host_name not in hamnet_dict:
                            hamnet_dict[alias_host_name] = Resource_record(content=host_name, type="CNAME", ttl=600)
                            if alias_host_name.endswith('-global.'+site+'.hamip.at.'):
                                # print("found")
                                special_host = alias_host_name.replace('-global.'+site+'.hamip.at.', "") + hamip_at
                                # print(f"special host {special_host}")
                                if special_host not in hamnet_dict:
                                    hamnet_dict[special_host] = Resource_record(content=host_name, type="CNAME",
                                                                                ttl=600)

        site_list.sort()
        for site in site_list:
            site_domain = site + hamip_at
            if site_domain not in hamnet_dict:
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

        # Show the results
        if DEBUG:
            print(f"Dictionary: {len(hamnet_dict)}")
        # print(json.dumps(hamnet_dict, indent=2))

    except json.JSONDecodeError:
        raise NameError("Failed to decode JSON data")


def get_hamnetdb_dhcp(dhcp_dict, hosts_dict, hamip_at):
    # Endpoint for HamnetDB subnets
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

    DEBUG = False

    # convert hosts-dict into and ip-dict
    ip_dict = {}
    for host in hosts_dict:
        if hosts_dict[host].type == 'A':
            index = host.rfind(hamip_at)
            site = host[host.rfind('.', 0, index - 1) + 1:]
            ip_dict[hosts_dict[host].content] = site

    if DEBUG:
        print(ip_dict)

    try:
        response = requests.get(HAMNETDB_ENDPOINT)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        if DEBUG:
            print(f"Error fetching data from HamnetDB: {e}")
        raise NameError("Failed to decode JSON data")

    try:
        data = response.json()
        if DEBUG:
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

            # Convert the CIDR to an IP network and compile the list of IPs
            all_ips = []
            cidr = entry.get('ip', '')
            if DEBUG:
                print(cidr)
            if cidr:
                try:
                    network = ipaddress.ip_network(cidr, strict=False)
                    ips = [str(ip) for ip in network.hosts()]
                    all_ips.extend(ips)
                except ValueError as e:
                    print(f"Error processing CIDR {cidr}: {e}")
                    continue

            suffix = 'dhcp-range'+hamip_at

            # get suffix from ip list (using e.g. "dhcp-44-143-33-179.oe2wao-1.hamip.at.")
            suffix_found = False
            for ip in all_ips:
                if ip in ip_dict:
                    suffix = ip_dict[ip]
                    suffix_found = True
                    break

            if suffix_found:

                # Generate the dictionary entries
                for i in range(range_start, range_end + 1):
                    octets = base_ip.split('.')
                    octets[3] = str(i)  # Replace the last octet with each number in the range
                    ip = '.'.join(octets)
                    dhcp_dict[f"dhcp-{ip.replace('.', '-')}.{suffix}"] = (
                        Resource_record(content=ip, type="A", ttl=600))

    except (json.JSONDecodeError, ValueError) as e:
        print("Failed to decode JSON data or parse ranges:", e)
        raise NameError("Failed to decode JSON data")

    # Print the resulting dictionary
    # print(dhcp_dict)


def main():
    HAMIP_AT = '.hamip.at.'

    hosts_dict = {}
    start_time = time.time()
    get_hamnetdb_hosts(hosts_dict, HAMIP_AT)
    # for key in hosts_dict:
    #     print(f"{key}: {hosts_dict[key]}")
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Function execution time: {elapsed_time:.6f} seconds")

    dhcp_dict = {}
    start_time = time.time()
    get_hamnetdb_dhcp(dhcp_dict, hosts_dict, HAMIP_AT)
    # for key in dhcp_dict:
    #    print(f"{key}: {dhcp_dict[key]}")
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Size of dhcp_dict: {len(dhcp_dict)}")
    print(f"Function execution time: {elapsed_time:.6f} seconds")


# only execute main if not imported
if __name__ == "__main__":
    main()
