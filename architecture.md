# Architecture

This document describes the scripts that build and maintain the **hamip.at** DNS
zone, and records known issues / findings from a code review.

## Overview

The `hamip.at` zone maps Austrian amateur-radio (HamNet) host names to IP
addresses. The source of truth is [HamnetDB](https://hamnetdb.net/); a set of
Python scripts pull the Austrian (`oe*`) data from HamnetDB, merge in locally
maintained static records, and push the result into two independent PowerDNS
instances via the [PowerDNS HTTP API](https://doc.powerdns.com/authoritative/http-api/):

- a **public Internet** zone, served by an ISP (netplanet) running PowerDNS, and
- a **HamNet "intranet"** zone, served by a local PowerDNS master and distributed
  across multiple servers using *AnyCast* + DNS zone transfer (AXFR).

The two zones are technically independent; in most cases their records are
identical so a dual-homed user does not depend on the HamNet zone.

```
HamnetDB (csv.cgi JSON API)
        |
        |  hamnetdb_util.py  (fetch hosts + DHCP, build records)
        v
   in-memory record dict  +  static_records.yaml
        |
        |  update.py  (diff against live zone)
        v
  powerdns_util.py  (PATCH/PUT via PowerDNS HTTP API)
        |
        +--> public zone   (ISP PowerDNS)
        +--> HamNet zone   (local PowerDNS -> AnyCast/AXFR)
```

## Scripts

All scripts live in `hamip.at/`.

### `update.py` — main entry point

Orchestrates the whole update. It:

1. Builds the desired record set from HamnetDB (`get_hamnetdb_hosts`, optionally
   `get_hamnetdb_dhcp`).
2. Reads the PowerDNS API keys from `/etc/hamip/key.asc` (ISP) and
   `/etc/hamip/key_hamnet.asc` (HamNet).
3. Loads locally maintained static records from
   `/etc/hamip/static_records.yaml` (separate `isp` and `hamnet` sections).
4. Adds a `timestamp.hamip.at.` TXT record so every run bumps the zone serial.
5. For each target (ISP, then HamNet): fetches the current zone, diffs it against
   the desired record set, and applies the differences as chunked PATCH requests
   (deletes first, then changes/additions), finally incrementing the SOA serial.

Key constants (endpoints, key paths, static-records path) are defined at the top
of the file. `DEBUG` enables verbose output.

### `hamnetdb_util.py` — HamnetDB data source

Fetches and transforms HamnetDB data into a dict of
`Resource_record(type, content, ttl)` keyed by FQDN:

- `get_hamnetdb_hosts()` — pulls the `host` table, filters to Austrian sites
  (`site` starting with `oe`), and creates:
  - `A` records for each host name,
  - `CNAME` records for each alias,
  - special handling for `*.oe0any.*` and `*-global.<site>.*` names,
  - a per-site `CNAME` (e.g. `oe3xnr.hamip.at.`) pointing at a sensible target
    (`www.`/`web.`/`bb.`/`router.` host, or any other host under the site).
- `get_hamnetdb_dhcp()` — pulls the `subnet` table and expands each subnet's
  `dhcp_range` into individual `dhcp-<ip>.<site>` A records. (Disabled by default
  via `USE_DHCP = False` in `update.py`.)

Running this module directly executes a small benchmark via `main()`.

### `powerdns_util.py` — PowerDNS HTTP API client

Thin wrappers around the PowerDNS authoritative HTTP API for the `hamip.at` zone:

- `get_zone()` / `get_zones()` — fetch zone metadata / locate the zone id.
- `get_current_zone()` — return the live zone as a dict of `Resource_record`,
  keeping only `A`, `CNAME` and `TXT` records (so infrastructure records such as
  SOA/NS are left untouched).
- `request_patch()` — send an rrset PATCH (REPLACE/DELETE) and verify the
  expected status code.
- `update_serial()` — PUT `soa_edit_api = INCREASE` to bump the serial.

### `get_dns_zone_util.py` — zone reader (utility)

Performs an AXFR zone transfer with `dnspython` and returns/prints all records as
`(name, ttl, class, type, value)` tuples. Useful for inspecting/verifying a live
zone. Requires `dnspython`.

### `pubip_util.py` — public-IP name parser (prototype)

Prototype to embed a public Internet IP in a HamnetDB name. A name of the form
`185-236-164-044-inetip.wx.oe3gwu.hamip.at.` is parsed into the IP
`185.236.164.44` and domain `wx.oe3gwu.hamip.at.`, the intent being to create the
corresponding A record. Not yet wired into `update.py`.

## Configuration / runtime inputs

- `/etc/hamip/key.asc` — PowerDNS API key for the ISP (public) instance.
- `/etc/hamip/key_hamnet.asc` — PowerDNS API key for the local HamNet instance.
- `/etc/hamip/static_records.yaml` — locally maintained records, with top-level
  `isp:` and `hamnet:` mappings; each entry has `type`, `content`, `ttl`.

## Tests

Unit tests live in `tests/` and use the standard-library `unittest` framework
(no extra dependencies). They are self-contained — all HamnetDB HTTP calls are
mocked, so the suite runs offline.

Run them from the repository root:

```
python -m unittest discover -s tests -v
```

`tests/conftest.py` adds the `hamip.at/` directory to `sys.path` so the
non-package modules can be imported.

- `tests/test_pubip_util.py` — covers `extract_ip_and_domain`: zero-padded and
  non-padded octets, out-of-range octets, the all-zeros / max-value boundaries,
  and non-matching input.
- `tests/test_hamnetdb_util.py` — covers the record-building logic of
  `get_hamnetdb_hosts` (A records, alias CNAMEs, the per-site CNAME target
  selection, `oe0any` special hosts, deleted-entry and non-Austrian filtering)
  and the DHCP range expansion in `get_hamnetdb_dhcp`, with `requests.get`
  patched to return canned payloads.

