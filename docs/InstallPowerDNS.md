# How to install and setup PowerDNS

The setup consists of a local HamNet-PowerDNS server running as master for Hamnet and a remote PowerDNS server serving
in the public Internet.
The remote server is hosted by an ISP, the only local configuration is the setup of the API (endpoint URL and key).

## Local PowerDNS instance

The local instance uses Debian and Sqlite3 as database backend.

### Installation of packages

Install packages required for PowerDNS:

    apt -y install pdns-server pdns-backend-sqlite3 pdns-utils sqlite3 pwgen 
    apt -y remove pdns-backend-bind

Setup port 8053 instead of port 53 in `/etc/powerdns/pdns.conf` by adding (uncommenting) `local-port = 8053`.
Remove `/etc/powerdns/pdns.d/bind.conf` (Backend configuration for the not used bind-backend)

### Initial configuration of PowerDNS

Setup SQLite3 in `/etc/powerdns/pdns.conf` by adding: 

    launch=gsqlite3 
    gsqlite3-database=/var/lib/powerdns/pdns.sqlite3

Next database setup:

    mkdir /var/lib/powerdns
    sqlite3 /var/lib/powerdns/pdns.sqlite3 < /usr/share/doc/pdns-backend-sqlite3/schema.sqlite3.sql
    chown -R pdns:pdns /var/lib/powerdns

Restart database and check log:

Make a query:

    dig a www.example.com @127.0.0.1 -p8053 

## Create zone "hamip.at"

    sudo -u pdns pdnsutil create-zone hamip.at ns.hamip.at

> Creating empty zone 'hamip.at'
> Also adding one NS record

You may now play with zone settings
> sudo -u pdns pdnsutil edit-zone hamip.at

### API key
To allow API access an key needs to be set:

    api=yes
    api-key=change-me
    webserver=yes
    webserver-address=127.0.0.1

Generate the key with 

    pwgen -s -1 16

Restart PowerDNS

Note: On public installations the API key is restricted to a single domain by a reverse-proxy, but
that is not part of PowerDNS, thus in our installation the key can do all but is restricted to localhost.

#### Check zone via API

    curl -v -H 'X-API-Key: change-me' http://127.0.0.1:8081/api/v1/servers/localhost/zones | jq .


# References
* https://doc.powerdns.com/authoritative/guides/basic-database.html
* https://doc.powerdns.com/authoritative/installation.html
