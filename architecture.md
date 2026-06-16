# Architecture

This document describes the `hamipat` package that builds and maintains the
**hamip.at** DNS zone.

## Overview

The `hamip.at` zone maps Austrian amateur-radio (HamNet) host names to IP
addresses. The source of truth is [HamnetDB](https://hamnetdb.net/); the package
pulls the Austrian (`oe*`) data from HamnetDB, merges in locally maintained
static records, and pushes the result into two independent PowerDNS instances via
the [PowerDNS HTTP API](https://doc.powerdns.com/authoritative/http-api/):

- a **public Internet** zone, served by an ISP (netplanet) running PowerDNS, and
- a **HamNet "intranet"** zone, served by a local PowerDNS master and distributed
  across multiple servers using *AnyCast* + DNS zone transfer (AXFR).

The two zones are technically independent; in most cases their records are
identical so a dual-homed user does not depend on the HamNet zone.

```
HamnetDB (csv.cgi JSON API)
        |
        |  HamnetDbClient        (fetch hosts + DHCP, build records)
        v
   RecordMap (FQDN -> ResourceRecord)  +  static_records.yaml  +  timestamp TXT
        |
        |  ZoneUpdater           (diff reference against live zone)
        v
   PowerDnsClient               (PATCH/PUT via PowerDNS HTTP API)
        |
        +--> public zone   (ISP PowerDNS)
        +--> HamNet zone   (local PowerDNS -> AnyCast/AXFR)

   cli.run() wires the above together for each Target.
```

## Design

The code is a small Python package, `hamipat/`, organised by responsibility.
Two design choices make it easy to test and extend:

- **`ResourceRecord` is a frozen dataclass value object** (`records.py`). The
  whole zone is a `RecordMap` (`Dict[str, ResourceRecord]`), and records compare
  by value — which is exactly what the zone diff relies on.
- **The HTTP clients are objects with an injectable `session`.** `HamnetDbClient`
  and `PowerDnsClient` default to the `requests` module but accept any object
  exposing `.get`/`.patch`/`.put`, so the data-shaping and diff logic is unit
  tested without network access.

### Package layout (`hamipat/`)

| Module | Responsibility |
| --- | --- |
| `records.py` | `ResourceRecord` value object and the `RecordMap` type alias. |
| `config.py` | Constants (endpoints, URLs, paths), the `Target` dataclass, and `read_api_key()`. |
| `hamnetdb.py` | `HamnetDbClient` — fetch HamnetDB data and build the desired record set. |
| `powerdns.py` | `PowerDnsClient` — read/patch a PowerDNS zone; `PowerDnsError`. |
| `static_records.py` | `load_static_records()` — read the `isp`/`hamnet` YAML sections. |
| `updater.py` | `ZoneUpdater` — diff a desired `RecordMap` against the live zone and apply it. |
| `cli.py` | `run()` / `main()` — orchestrate an update across all `Target`s. |
| `pubip.py` | `extract_ip_and_domain()` — parse a public IP embedded in a name (prototype). |
| `zone_reader.py` | `load_dns_zone()` — read a zone over AXFR (diagnostics). |
| `__main__.py` | Enables `python -m hamipat`. |

### `HamnetDbClient` (`hamnetdb.py`)

Fetches and transforms HamnetDB data into a `RecordMap`:

- `fetch_hosts()` — pulls the `host` table, filters to Austrian sites (`site`
  starting with `oe`), and creates:
  - `A` records for each host name,
  - `CNAME` records for each alias,
  - special handling for `*.oe0any.*` and `*-global.<site>.*` names,
  - a per-site `CNAME` (e.g. `oe3xnr.hamip.at.`) pointing at a sensible target
    (`www.`/`web.`/`bb.`/`router.` host, or any other host under the site).
- `fetch_dhcp(hosts)` — pulls the `subnet` table and expands each subnet's
  `dhcp_range` into individual `dhcp-<ip>.<site>` A records, deriving the site
  suffix from `hosts`. (Disabled by default via `USE_DHCP = False` in `config.py`.)

A network failure now propagates (rather than silently yielding an empty record
set), so a fetch error aborts the run instead of risking a near-empty zone.

### `PowerDnsClient` (`powerdns.py`)

Object wrapper around the PowerDNS authoritative HTTP API for one zone:

- `fetch_zone()` — return the raw zone document (metadata + rrsets).
- `parse_records(zone)` — extract the managed records (`A`, `CNAME`, `TXT`) from a
  zone document, leaving infrastructure records such as SOA/NS untouched.
- `fetch_records()` — `parse_records(fetch_zone())` convenience.
- `replace_records()` / `delete_records()` — apply REPLACE/DELETE rrset patches in
  chunks (`chunk_size`, default 500).
- `increase_serial()` — PUT `soa_edit_api = INCREASE` to bump the serial.

Unexpected API responses raise `PowerDnsError`.

### `ZoneUpdater` (`updater.py`)

Given a `PowerDnsClient` (or any compatible object) and a desired `RecordMap`,
`sync(reference)` fetches the live zone once, validates it has a serial and is
non-empty, computes the removals and changes, applies deletes then
changes/additions, and bumps the serial. Returns the `(to_remove, to_change)`
maps it applied.

### `cli.py`

`run()` builds the HamnetDB record set once, loads the static records, then for
each `Target` reads its API key, assembles the reference set
(`hamnetdb | static | timestamp`), and calls `ZoneUpdater(client).sync(...)`.
`main()` configures logging and calls `run()`.

## Configuration / runtime inputs

Defaults live in `hamipat/config.py`:

- `/etc/hamip/key.asc` — PowerDNS API key for the ISP (public) instance.
- `/etc/hamip/key_hamnet.asc` — PowerDNS API key for the local HamNet instance.
- `/etc/hamip/static_records.yaml` — locally maintained records, with top-level
  `isp:` and `hamnet:` mappings; each entry has `type`, `content`, `ttl`. See
  `hamipat/static_records-example.yaml` for the format.

## Running

After `pip install .` (or `pip install -e .`):

```
hamip-update          # console-script entry point
python -m hamipat     # equivalent
```

## Tests

Unit tests live in `tests/` and use the standard-library `unittest` framework
(no extra dependencies). They are self-contained — all HTTP access is faked via
injected sessions / fake clients, so the suite runs offline.

Run them from the repository root:

```
python -m unittest discover -s tests -v
```

`tests/conftest.py` puts the repository root on `sys.path` so the `hamipat`
package can be imported in place.

- `tests/test_pubip.py` — `extract_ip_and_domain`: zero-padded and non-padded
  octets, out-of-range octets, the all-zeros / max-value boundaries, no match.
- `tests/test_hamnetdb.py` — `HamnetDbClient.fetch_hosts` (A records, alias
  CNAMEs, per-site CNAME target selection, `oe0any` special hosts, deleted-entry
  and non-Austrian filtering) and `fetch_dhcp` range expansion, with a fake
  session.
- `tests/test_powerdns.py` — `PowerDnsClient.parse_records` type filtering and the
  REPLACE/DELETE patch payload format and chunking, with a recording session.
- `tests/test_updater.py` — `ZoneUpdater.sync` diff logic (removals/changes,
  serial bump) and its error guards, with a fake client.
