# hamnetdb_util.py
import json
import time
from collections import namedtuple

import requests

# Utilities requesting data from the Hamnet-DB


Resource_record = namedtuple("Resource_record", ["type", "content", "ttl"])
def get_hamnetdb_hosts(hamnet_dict, hamip_at):
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

    DEBUG = False

    try:
        response = requests.get(HAMNETDB_ENDPOINT)
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
                            #if alias_host_name.endswith('.oe0any.hamip.at.'):
                            #    special_host = host_name.replace(".oe0any", "")
                            #    if special_host not in hamnet_dict:
                            #        hamnet_dict[special_host] = Resource_record(content=host_name, type="CNAME", ttl=600)
                            # news-global.oe1xqu.hamip.at => news.hamip.at
                            # print(f"got alias {alias_host_name} with site {site}")
                            if alias_host_name.endswith('-global.'+site+'.hamip.at.'):
                                # print("found")
                                special_host = alias_host_name.replace('-global.'+site+'.hamip.at.', "") + hamip_at
                                # print(f"special host {special_host}")
                                if special_host not in hamnet_dict:
                                    hamnet_dict[special_host] = Resource_record(content=host_name, type="CNAME", ttl=600)

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
        print("Failed to decode JSON data")

# util main
HAMIP_AT = '.hamip.at.'
some_dict = {}
start_time = time.time()
get_hamnetdb_hosts(some_dict, HAMIP_AT)
for key in some_dict:
    print(f"{key}: {some_dict[key]}")
end_time = time.time()
elapsed_time = end_time - start_time
print(f"Function execution time: {elapsed_time:.6f} seconds")