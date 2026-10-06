# Net-monit V10.6 — Admin Guide

This guide covers day-to-day administration: configuring alerts, adding monitored devices/services, managing users, and using the Admin panel. For installation, see the Setup Guide. For a plain end-user walkthrough of the dashboard, see the User Guide.

## 1. Signing in

Log in with your admin account at `http://<server>:50106`. Admin accounts can see the Admin panel (top nav) and every Settings tab; regular user accounts see the dashboard and monitoring pages but not user management or SMTP/escalation configuration.

## 2. Adding devices to monitor

**Devices page** (network hardware and servers):
1. Click **Add Device**.
2. Give it an ID, name, and host (IP or hostname).
3. Pick a **method**:
   - **Ping** — simple reachability + latency + packet loss. No credentials needed.
   - **SNMP** — for switches/routers/printers that expose SNMP. Needs a community string.
   - **PowerShell** — for Windows servers: CPU/memory/disk usage, over WinRM. Needs a Windows username/password with remote-management rights on the target, and "Remote" checked if this isn't the machine Net-monit itself runs on.
   - **SSH** — the Linux equivalent of PowerShell: CPU/memory/disk over an SSH connection. Needs a username + password or private key path.
   - **Shared drive** — free-space monitoring on a Windows UNC path or a Linux mount point.
4. **New in V8.2 — Watch services / scheduled tasks:** if you picked SSH or PowerShell, an extra section appears letting you list service names (Windows: as shown in `services.msc`, e.g. `Spooler`; Linux: systemd unit names, e.g. `nginx`) and/or scheduled task names (Windows: full Task Scheduler path, e.g. `\Backup\NightlyBackup`; Linux: systemd timer name) to watch on that same host. This reuses the SSH/PowerShell credentials you already entered above — no separate login needed. **Any single watched service or task that's stopped/failed marks the whole device Critical.** This is only offered for SSH/PowerShell devices, since those are the only methods with a credential path to actually query the host's services/tasks.
5. Click **Test** before saving to confirm the connection and credentials actually work.
6. Save.

**Sites Monitor page** (URLs / web applications):
1. Go to **Sites Monitor** (separate from the Devices page — URLs and network devices are managed on their own dedicated pages).
2. Add a URL, expected HTTP status (default 200), and whether to verify the SSL certificate.
3. Net-monit will track response time, HTTP status code, page size, and SSL certificate expiry (an expiring/expired cert can affect the site's overall status, not just show as a side note).

You can also quickly add either kind of device from the **Dashboard** itself via **+ Add Tile**, which offers the same options in a lighter-weight modal — useful when you just want to get something onto the dashboard fast without leaving it.

## 3. Alerting — how it works and how to tune it

### 3.1 Thresholds

Every numeric metric (CPU%, memory%, disk%, latency, packet loss, and — new in V8.2 — website response time) has a **warning** and **critical** threshold. There's a sensible built-in default for each; override globally (Settings) or per-device (device edit form) if a particular server or site needs different limits.

### 3.2 Alert trigger mode — NEW in V8.2

This is the feature for controlling *when* the first alert email actually fires, separate from thresholds (which control *whether* something counts as a problem at all). Found in **Settings → Escalation** (global default) and in each device's **Notify** modal (per-device override).

- **Immediate** (default): the moment a device/site crosses a threshold or goes offline, an email goes out. This is how every version before V8.2 behaved, and it's still the default so upgrading doesn't silently change your alert timing.
- **Wait to confirm, then alert**: no email on the very first detection. Instead, the problem has to still be present once your **Level 1 escalation time** has elapsed (see below) before anything gets emailed. A brief blip — say, 5 seconds of packet loss on a site that then recovers on its own — still shows up in the **Alert Event Log**, it just never reaches anyone's inbox. If it's *still* broken once L1 time passes, exactly one email fires at that point, and escalation continues from there exactly as it would in Immediate mode.

**Example matching what most people want:** set the global mode to "Wait to confirm", and set Level 1 to 30 seconds. A device that blips for a few seconds and recovers generates no email at all (just a log entry); a device that's actually down for 30+ seconds generates exactly one confirmed alert email, with Level 2/3 escalation continuing on top if it stays down even longer.

### 3.3 Escalation levels (L1/L2/L3)

Each level has its own delay (seconds since the problem started) and its own list of email recipients — so, for example, Level 1 might notify the on-call engineer after 30 seconds, Level 2 might add the team lead after 10 minutes, and Level 3 might add management after 30 minutes. Toggle each level on/off independently. **"Apply to all devices"** pushes your current L1/L2/L3 timers, email lists, and alert trigger mode out to every device at once (per-device threshold overrides are left alone by this button — it only touches timing/emails/trigger mode).

### 3.4 Acknowledging vs. resolving

In the **Alert Event Log**:
- **Acknowledge** — "I've seen this, stop escalating it for now." Suppresses further escalation emails for that specific device+metric until the end of the current day (23:59:59), after which it automatically reopens as a fresh incident if the problem is still there.
- **Resolve** — manually marks it closed. If the underlying problem is actually still happening, the next monitoring poll will simply detect it again and reopen a new incident — resolving doesn't "silence" anything ongoing, it just clears the current entry.

## 4. Network Scan

Sweeps a subnet (e.g. `192.168.1.0/24`) for live hosts: ping, common-port probing to guess device type, reverse-DNS hostname, and MAC address + vendor lookup. Use **Add** on any discovered host to promote it into a monitored Device without re-typing its IP.

**On MAC/vendor detection:** Net-monit reads your machine's own ARP table to find MAC addresses (this doesn't require any special permissions, unlike a raw packet capture). A device that hasn't exchanged any network traffic with this machine yet may not have a MAC visible on the first scan — re-scanning after those devices have been pinged usually resolves it. Vendor names come from a built-in list of common manufacturer prefixes (a few hundred entries covering the vendors people actually run into on a LAN — Cisco, HP, Dell, Netgear, Ubiquiti, Apple, and so on) rather than the complete official registry, so an unusual or newer device may show a MAC with no vendor name attached; that's expected, not a malfunction.

## 5. Dashboard layout (for your own view)

The Dashboard's Edit Mode (drag tiles, resize, hide/show, switch Grid/List view and column density) is **saved per admin account**, so your layout doesn't affect what other users see, and correctly persists across refreshes and logins as of V8.2.

## 6. User management (Admin panel)

Create/edit/deactivate accounts, assign the `admin` or `user` role. Regular users can view dashboards and monitoring pages but can't touch SMTP, escalation, or user management. The **audit log** in the Admin panel records administrative actions (user changes, settings changes) with who/what/when.

## 7. SMTP configuration

Settings → SMTP: host, port, credentials, and the "from" address alert emails will be sent from. Send a test email after saving to confirm delivery before relying on it — some networks block outbound mail ports by default, which is the most common reason alert emails silently never arrive.

## 8. Backups

Everything that matters lives in two places: `config.yaml` (devices, SMTP, thresholds, escalation defaults) and `data/monitor.db` (users, alert history, per-user dashboard layout, license state). Back up both together, on the same schedule — they're not useful independently of each other.
