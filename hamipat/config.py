"""Static configuration and small configuration helpers."""
import os
from dataclasses import dataclass

# DNS zone served by this tooling.
ZONE_NAME = "hamip.at"
# Suffix appended to bare HamnetDB names to form an FQDN (note leading/trailing dot).
HAMIP_AT = ".hamip.at."

# HamnetDB CSV/JSON export endpoints.
HAMNETDB_HOST_URL = "https://hamnetdb.net/csv.cgi?tab=host&json=1"
HAMNETDB_SUBNET_URL = "https://hamnetdb.net/csv.cgi?tab=subnet&json=1"

# Locally maintained static records (YAML with `isp:` and `hamnet:` sections).
STATIC_ZONES_LOCATION = "/etc/hamip/static_records.yaml"

# Whether to expand HamnetDB DHCP ranges into individual A records.
USE_DHCP = False


@dataclass(frozen=True)
class Target:
    """A PowerDNS instance to update."""

    name: str
    endpoint: str
    api_key_path: str
    is_hamnet: bool


ISP_TARGET = Target(
    name="ISP",
    endpoint="https://dnsapi.netplanet.at/api",
    api_key_path="/etc/hamip/key.asc",
    is_hamnet=False,
)

HAMNET_TARGET = Target(
    name="HamNet",
    endpoint="http://127.0.0.1:8081/api",
    api_key_path="/etc/hamip/key_hamnet.asc",
    is_hamnet=True,
)

DEFAULT_TARGETS = (ISP_TARGET, HAMNET_TARGET)


def read_api_key(file_path):
    """Read an API key from ``file_path``.

    Returns the stripped key, or ``None`` if the file is missing, empty or
    cannot be read.
    """
    try:
        if not os.path.isfile(file_path):
            return None
        with open(file_path, "r") as handle:
            key = handle.read().strip()
        return key or None
    except OSError:
        return None
