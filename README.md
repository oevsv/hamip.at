# hamip.at
Documentation and code related to the domain hamip.at used for the Austrian amateur radio IP networks

## Architecture

The setup is built around [HamnetDB](https://https://hamnetdb.net/).
That database collects and organizes information for HamNet hosts and links.

Information for the HamnetDB is collected through the [HamnetDB-API](https://hamnetdb.net/?m=util).

A script processes the Austrian data and creates *hamip.at*.

## Internet

In the Internet, the DNS zone *hamip.at* is provided by an ISP running PowerDNS.
The script updates the DNS-records using the [PowerDNS-API](https://doc.powerdns.com/authoritative/http-api/).

## Hamnet

In Hamnet *AnyCast* is used to make DNS the zone *hamip.at* available on multiple servers.
That "intranet" zone uses a local instance of PowerDNS as master.
*AnyCast* itself does not depend on PowerDNS but uses DNS-style zone transfer (AXFR) to distribute the *hamip.at* zone.

Technically the public Internet-zone *hamip.at* and the "intranet" zone *hamip.at* are independent of
each other. In most cases the records are identical, thus a *dual homed* user does not depend on the Hamnet zone.

