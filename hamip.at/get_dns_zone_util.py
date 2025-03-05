# requires dnspython3
import dns.query
import dns.zone


def load_dns_zone(zone_name, nameserver,port=53):
    try:
        # Perform a zone transfer (AXFR) request
        zone = dns.zone.from_xfr(dns.query.xfr(nameserver, zone_name,port=port))

        # Collect all records from the zone into a tuple
        records = []
        for name, node in zone.nodes.items():
            rdatasets = node.rdatasets
            for rdataset in rdatasets:
                ttl = rdataset.ttl
                record_class = dns.rdataclass.to_text(rdataset.rdclass)
                record_type = dns.rdatatype.to_text(rdataset.rdtype)
                for rdata in rdataset:
                    value = rdata.to_text()
                    # Append a tuple with the DNS record details
                    records.append((name.to_text(), ttl, record_class, record_type, value))

        return tuple(records)

    except Exception as e:
        print(f"Failed to load DNS zone: {e}")
        return ()

# Example usage
def main():
    # Example usage
    zone_name = "hamip.at"
    nameserver = "44.143.0.10"
    dns_zone_records = load_dns_zone(zone_name, nameserver)

    # Output the loaded DNS zone records
    for record in dns_zone_records:
        # Print in format: name ttl class type value
        print(f"{record[0]:<30} {record[1]:<6} {record[2]:<5} {record[3]:<6} {record[4]}")



# only execute main if not imported
if __name__ == "__main__":
    main()