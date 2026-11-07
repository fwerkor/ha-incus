"""Constants for the Incus integration."""

from datetime import timedelta

DOMAIN = "incus"
CONF_CERT_PATH = "cert_path"
CONF_KEY_PATH = "key_path"
CONF_CA_PATH = "ca_path"
CONF_VERIFY_SSL = "verify_ssl"
CONF_PROJECT = "project"

DEFAULT_PORT = 8443
DEFAULT_PROJECT = "*"
SCAN_INTERVAL = timedelta(seconds=60)
