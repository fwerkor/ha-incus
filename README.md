# ha-incus

[![CI](https://github.com/fwerkor/ha-incus/actions/workflows/test.yml/badge.svg)](https://github.com/fwerkor/ha-incus/actions/workflows/test.yml)

A Home Assistant custom integration for [Incus](https://linuxcontainers.org/incus/) containers and virtual machines, providing a Proxmox-style overview and controls.

**Status:** Community preview. Automated tests use mock Incus API responses. Real Incus and Home Assistant installations have not yet been verified.

## Features

- Configure Incus from **Settings → Devices & services → Add integration → Incus**.
- Automatically discover containers and VMs from a project or from all accessible projects.
- Create a device for each instance, grouped under an Incus server device.
- Show instance status, running state, CPU usage and time, memory, root disk, network I/O, process count and uptime.
- Provide an instance **Power** switch, plus Start/Stop/Restart action buttons (buttons are disabled by default; enable them in the entity registry).
- Show server-wide running and total instance counts.
- Refresh every 60 seconds and add newly discovered instances without restarting Home Assistant.
- English and Simplified Chinese config translations.

> Incus is not Proxmox VE. Metrics are reported only when the Incus API provides them; unsupported values show as *unknown*. The CPU percentage is based on successive Incus CPU-time samples and `allocated_time`, and is unavailable when the server does not expose the latter.

## Requirements

- A Home Assistant installation (2025.6 or later).
- An Incus server with the remote HTTPS API enabled.
- An Incus **trusted TLS client certificate** and matching private key. The certificate must have sufficient instance permissions.
- Reachability from Home Assistant to the Incus HTTPS port (normally TCP 8443).

### Enable the Incus API

On the Incus host, if remote HTTPS is not already enabled:

```sh
incus config set core.https_address :8443
```

Do **not** expose the Incus API directly to untrusted networks. Restrict it using a firewall, VPN or private LAN. Grant the TLS certificate only the Incus permissions you intend Home Assistant to have.

### Generate a client certificate

Run these commands **on a trusted computer**, then securely copy the two files to the Home Assistant config directory, for example `/config/incus/`. Do not commit private keys to Git.

```sh
openssl req -x509 -newkey rsa:3072 -nodes -days 365 -sha256 \
  -keyout incus-client.key -out incus-client.crt -subj "/CN=HomeAssistant-Incus"
chmod 600 incus-client.key
```

On the Incus server, add **only the public client certificate**:

```sh
incus config trust add-certificate incus-client.crt
```

The `add-certificate` command requires the public certificate file on the Incus host. Prefer a restricted certificate under Incus fine-grained authorization when available; an unrestricted trusted client certificate can control all Incus instances.

For verifying a self-signed Incus server, obtain its public server certificate (`/var/lib/incus/server.crt` on typical installations) via a trusted channel and place it under `/config/incus/server.crt`. Avoid disabling TLS verification. If you are using a publicly trusted server certificate, you can leave the CA path blank.

### Install

**HACS:** Open HACS → the menu → **Custom repositories**, paste `https://github.com/fwerkor/ha-incus`, select **Integration**, install it and restart Home Assistant.

**Manual:** Copy `custom_components/incus` to `<HA config>/custom_components/incus` and restart Home Assistant.

Then go to **Settings → Devices & services → Add integration**, search `Incus`, and enter:

| Field | Example |
| --- | --- |
| Host | `incus.example.lan` |
| Port | `8443` |
| Client certificate path | `/config/incus/incus-client.crt` |
| Client private key path | `/config/incus/incus-client.key` |
| Server CA certificate path | `/config/incus/server.crt` |
| Verify TLS certificate | `On` (recommended) |
| Project | `*` for all accessible projects, or `default` |

These paths refer to the **Home Assistant filesystem**, not the Incus host. Certificate contents are never stored in the Home Assistant config entry (only file paths are).

## Operations and safety

- The power switch and action buttons call `PUT /1.0/instances/{name}/state` with the correct Incus project.
- Shutdown and restart use graceful operations with a 30-second timeout; there is no force-stop button.
- A command only succeeds after the Incus asynchronous operation finishes successfully.
- Running a Home Assistant automation with the power switch requires trusting that automation with instance control.
- The integration does not create, delete, modify configuration, back up or migrate instances.
- The project filter `*` requires the Incus API to allow `all-projects=true`.

## Development

```sh
python -m pip install -r requirements-test.txt
ruff check .
pytest -q
```

The integration uses the standard Home Assistant config-entry APIs, with an independent TLS-authenticated aiohttp session per server. No Incus API tokens or private keys are uploaded to GitHub.

## License

MIT
