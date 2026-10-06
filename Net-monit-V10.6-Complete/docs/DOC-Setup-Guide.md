# Net-monit V10.6 — Setup Guide

This guide walks through installing Net-monit V10.6 on a Windows or Linux machine. It's written for whoever is doing the install — usually an IT admin — and assumes no prior familiarity with the product.

## Before you start

- **One machine on your network** to host Net-monit (Windows 10/11/Server, or a modern Linux distribution). This machine will do the monitoring — it needs network access to whatever you want to monitor, outbound SMTP access for email alerts, outbound HTTPS for SMS/voice gateway alerts, and outbound HTTPS to speed.cloudflare.com if end users will use the browser-based "Test Your PC Speed" speed test.
- **Port 50106** must be free on that machine (this is Net-monit V10.6's port — note the port number *is* the version, so this differs from your previous version if you're upgrading, e.g. V8.8, which used 5088).
- **Python 3.10+** (the installer will check this on Windows; most Linux distributions already have it).
- **A license key** — see "Activation" below. You can also start a trial without one.

## Windows installation

1. **Copy the Net-monit V10.6 folder** to the machine (any location — the installer will offer to move it to `C:\NetMonit-V10.6` by default).
2. **Run `Setup.bat`** as Administrator. This launches the graphical setup wizard.
3. The wizard checks for Python, installs any missing pip dependencies, and asks where to install (default `C:\NetMonit-V10.6`).
4. If a previous Net-monit service is already running on this machine (e.g. you're upgrading from V8.8), the wizard **stops it first**, before making any changes — this ordering matters and is deliberate, so don't run the old and new versions' installers in parallel.
5. The wizard registers a Windows Service named `Net_Monit_V106` (via `sc.exe`), pointed at `pythonw.exe` so no console window stays open.
6. Once registration completes, the service starts automatically and the wizard opens your browser to `http://localhost:50106`.
7. **First-run:** you'll land on the Activation screen if no license/trial is active yet (see Activation below), otherwise straight to a login screen with a seeded default admin account — check the wizard's final screen, it displays the generated default admin password once, so **note it down before closing the wizard**.

### Alternate Windows path: PowerShell installer

If you prefer scripting the install (e.g. for imaging multiple machines), `setup/Setup-Windows.ps1` performs the same steps non-interactively. Run it from an elevated PowerShell prompt; it accepts the same install-directory parameter as the GUI wizard.

## Linux installation

1. Copy the Net-monit V10.6 folder to the target machine, e.g. `/opt/netmonit-v106-src` (temporary — the installer relocates it).
2. From that folder, run:
   ```bash
   sudo ./setup.sh
   ```
3. This installs Python dependencies (via `pip`), copies the application to `/opt/netmonit-v106`, and installs a **systemd service** named `netmonit-v106` (`scripts/linux/netmonit-v106.service`).
4. The installer enables and starts the service:
   ```bash
   sudo systemctl enable netmonit-v106
   sudo systemctl start netmonit-v106
   ```
5. Check it's running:
   ```bash
   sudo systemctl status netmonit-v106
   ```
6. Open `http://<this-machine's-IP>:50106` from any browser on the network.

## Activation

On first launch you'll see the Activation screen if there's no valid license yet. You have two options:

- **Start a trial** — no key needed, time-limited, gets you into the full product immediately to evaluate it.
- **Enter a license key** — you'll need your **Device ID** and **Activation Code** (both shown right there on the Activation screen — they're generated from this specific machine's hardware, which is *why* a license key is tied to one installation) plus the license key itself, which your vendor/product owner generates for you using those two values. (The Product Owner Guide that explains *how* to generate keys is a separate, vendor-only document — it isn't part of this package, so if you're the one installing Net-monit rather than issuing keys for it, you won't see it and don't need it. If you *are* the person issuing keys, your copy came from wherever you obtained the License Key Generator, not from this Setup Guide.)

## Upgrading to V10.6

If you're upgrading an existing V8.8, V10.0, V10.1, V10.2, V10.3, V10.4, **or** V10.5 install rather than doing a fresh install, the steps are the same either way — only which old service/port/directory you're moving from changes.

1. **Your existing data is safe.** No database columns were removed or renamed this release. Devices, alert history, and settings all carry over.
2. Because the port and service name change with every release (5088 → 50100 → 50101 → 50102 → 50103 → 50104 → 50105 → 50106; `Net_Monit_V88` → `Net_Monit_V100` → `Net_Monit_V101` → `Net_Monit_V102` → `Net_Monit_V103` → `Net_Monit_V104` → `Net_Monit_V105` → `Net_Monit_V106`), V10.6 installs **side-by-side** with whatever you had before rather than replacing it in place — the Windows/Linux installers will stop and remove the *old* service as part of installing the new one (see step 4 of the Windows section above), but the install directories are different (`C:\NetMonit-V8.8`, `C:\NetMonit-V10.0`, `C:\NetMonit-V10.1`, `C:\NetMonit-V10.2`, `C:\NetMonit-V10.3`, `C:\NetMonit-V10.4`, or `C:\NetMonit-V10.5`, vs. `C:\NetMonit-V10.6`), so keep your old install directory around until you've confirmed V10.6 is working, then remove it manually.
3. **Copy your `data/monitor.db` file** from the old install directory into the new one before first starting the V10.6 service, if you want to carry over devices, alert history, and settings. Alternatively, use the **Admin Panel → Backup & Restore** export/import feature from your old install before upgrading, and restore it once V10.6 is up — this is the recommended path.
4. Update any firewall rules that reference your old port (5088, 50100, 50101, 50102, 50103, 50104, or 50105) to also allow 50106.
5. If you're coming from V8.8 specifically: your admin account's access token upgrades automatically to a stronger storage format (PBKDF2, not the older plain SHA-256) the next time that account successfully logs in — nothing you need to do, it happens transparently on sign-in. If you're already on V10.0, V10.1, V10.2, V10.3, V10.4, or V10.5, this already happened.
6. **Check you are really on the new version.** After installing, the browser tab title and the About page must say **V10.6**, and the address must end in **:50106**. Every version keeps its own port, so an old bookmark (for example one ending in `:50105`) opens the *old* service, not the one you just installed. Also, Python does not pick up changed files while a service is running — if you ever copy new files over an existing install by hand, restart the service afterwards.
7. **V10.6 fixes WAN speed test accuracy.** "Test WAN Speed" could under-report badly on a fast connection — the test's parallel connections were being closed and reopened for every few megabytes instead of staying open for the whole test, and the faster your real connection, the more of the test was spent reconnecting rather than measuring. Fixed: connections now stay open for the full test. A separate compatibility issue that was silently blocking the more accurate, ISP-graded test method from running at all (on newer Python installs) is also fixed — where that method can now run successfully, WAN results should land noticeably closer to what a commercial speed test site reports for the same connection. "Test Your PC Speed" received a smaller, precautionary change in the same release; if its numbers still look wrong, treat that as a separate report — it isn't confirmed to have had the same problem.

   If you don't use the Speed Test page, V10.6 changes nothing else about how you use the product.

## Uninstalling

- **Windows:** run `Uninstall.bat` as Administrator (stops and removes the `Net_Monit_V106` service, offers to delete the install directory and data).
- **Linux:** run `scripts/linux/uninstall.sh` as root (stops, disables, and removes the systemd unit; offers to delete `/opt/netmonit-v106`).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Browser can't reach `http://localhost:50106` | Service isn't running — check `sc query Net_Monit_V106` (Windows) or `systemctl status netmonit-v106` (Linux). Also confirm nothing else is using port 50106. |
| Installer says Python not found (Windows) | Install Python 3.10+ from python.org and re-run `Setup.bat`. |
| Service starts then immediately stops | Check the log file in the install directory's `logs/` folder for the actual startup error — usually a missing pip dependency or a `config.yaml` syntax error. |
| Alert emails never arrive | Check Settings → SMTP is configured and saved, and that the host machine can reach your SMTP server on its configured port (some networks block outbound 25/587 by default). |
| SMS/call alerts never arrive | Check Settings → SMS & Call Alerts — use the "Send test" button there first; it surfaces the gateway's raw HTTP error, which is almost always more specific than "it didn't work." |
| "Test Your PC Speed" speed test fails but "Test WAN Speed" works fine | The end user's own network (not the server's) is blocking outbound HTTPS to `speed.cloudflare.com` — check their firewall/proxy/ad-blocker. This is expected behavior, not a bug: the two buttons test two different network paths. |
| Speed test "Hostname" column is blank | Expected on networks without reverse DNS configured for internal IPs (common on home/small-office networks, less common on a Windows AD domain) — the local IP is still shown even when the hostname can't be resolved. |
| Network Scan finds devices but MAC/vendor is blank for some | This is expected for devices Net-monit hasn't yet exchanged any traffic with (their entry isn't in this machine's ARP table yet) — re-running the scan after those devices have been contacted once usually fills it in. See the Admin Guide for more detail. |

For anything else, see the Admin Guide (day-to-day operation) or the User Guide (end-user features), both in this same `docs/` folder.
