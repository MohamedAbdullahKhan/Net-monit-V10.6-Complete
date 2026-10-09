# Net-monit V10.7 — Setup Guide

This guide walks through installing Net-monit V10.7 on a Windows or Linux machine. It's written for whoever is doing the install — usually an IT admin — and assumes no prior familiarity with the product.

## Before you start

- **One machine on your network** to host Net-monit (Windows 10/11/Server, or a modern Linux distribution). This machine will do the monitoring — it needs network access to whatever you want to monitor, outbound SMTP access for email alerts, outbound HTTPS for SMS/voice gateway alerts, and outbound HTTPS to speed.cloudflare.com if end users will use the browser-based "Test Your PC Speed" speed test.
- **Port 50107** must be free on that machine (this is Net-monit V10.7's port — note the port number *is* the version, so this differs from your previous version if you're upgrading, e.g. V8.8, which used 5088).
- **Python 3.10+** (the installer will check this on Windows; most Linux distributions already have it).
- **A license key** — see "Activation" below. You can also start a trial without one.

## Windows installation

1. **Copy the Net-monit V10.7 folder** to the machine (any location — the installer will offer to move it to `C:\NetMonit-V10.7` by default).
2. **Run `Setup.bat`** as Administrator. This launches the graphical setup wizard.
3. The wizard checks for Python, installs any missing pip dependencies, and asks where to install (default `C:\NetMonit-V10.7`).
4. If a previous Net-monit service is already running on this machine (e.g. you're upgrading from V8.8), the wizard **stops it first**, before making any changes — this ordering matters and is deliberate, so don't run the old and new versions' installers in parallel.
5. The wizard registers a Windows Service named `Net_Monit_V107` (via `sc.exe`), pointed at `pythonw.exe` so no console window stays open.
6. Once registration completes, the service starts automatically and the wizard opens your browser to `http://localhost:50107`.
7. **First-run:** you'll land on the Activation screen if no license/trial is active yet (see Activation below), otherwise straight to a login screen with a seeded default admin account — check the wizard's final screen, it displays the generated default admin password once, so **note it down before closing the wizard**.

### Alternate Windows path: PowerShell installer

If you prefer scripting the install (e.g. for imaging multiple machines), `setup/Setup-Windows.ps1` performs the same steps non-interactively. Run it from an elevated PowerShell prompt; it accepts the same install-directory parameter as the GUI wizard.

## Linux installation

1. Copy the Net-monit V10.7 folder to the target machine, e.g. `/opt/netmonit-v107-src` (temporary — the installer relocates it).
2. From that folder, run:
   ```bash
   sudo ./setup.sh
   ```
3. This installs Python dependencies (via `pip`), copies the application to `/opt/netmonit-v107`, and installs a **systemd service** named `netmonit-v107` (`scripts/linux/netmonit-v107.service`).
4. The installer enables and starts the service:
   ```bash
   sudo systemctl enable netmonit-v107
   sudo systemctl start netmonit-v107
   ```
5. Check it's running:
   ```bash
   sudo systemctl status netmonit-v107
   ```
6. Open `http://<this-machine's-IP>:50107` from any browser on the network.

## Activation

On first launch you'll see the Activation screen if there's no valid license yet. You have two options:

- **Start a trial** — no key needed, time-limited, gets you into the full product immediately to evaluate it.
- **Enter a license key** — you'll need your **Device ID** and **Activation Code** (both shown right there on the Activation screen — they're generated from this specific machine's hardware, which is *why* a license key is tied to one installation) plus the license key itself, which your vendor/product owner generates for you using those two values. (The Product Owner Guide that explains *how* to generate keys is a separate, vendor-only document — it isn't part of this package, so if you're the one installing Net-monit rather than issuing keys for it, you won't see it and don't need it. If you *are* the person issuing keys, your copy came from wherever you obtained the License Key Generator, not from this Setup Guide.)

## Optional: make the WAN speed test measure against a nearby server

**Why you might want this.** "Test WAN Speed" measures the route from the Net-monit machine to a test server, and by default that server is Cloudflare's. The result is therefore "how fast is my connection *to Cloudflare*". On some internet providers that route is slower than the provider's own network, which is why a site like speedtest.net — it tests against a server inside your provider — can show a higher number for the same line. Net-monit always tells you what it measured against: the Speed Test page shows the server name and the round-trip time in the status line, and in the **Target** column of the log. If you want the number to reflect a closer server, point Net-monit at one.

**What you need.** The web address of a *LibreSpeed-compatible* test server close to you: one your own IT team runs (LibreSpeed is free, open-source software that installs on any small server), or one your provider offers. The address is the folder that contains the two files `garbage.php` and `empty.php` — for example `https://speedtest.example.ae/`.

**Steps on Windows**

1. Open **File Explorer** and go to the Net-monit install folder (by default `C:\NetMonit-V10.7`).
2. Right-click the file `config.yaml`, choose **Open with**, then **Notepad**.
3. Near the top, find the block that starts with `# speedtest:` (it sits just above the line `server:`).
4. Delete the `#` and the single space after it at the start of these lines — keep every other space exactly as it is, because the indentation matters:
   ```
   speedtest:
     targets:
       - name: "HQ Dubai"
         url: "https://speedtest.example.ae/"
   ```
   Replace `HQ Dubai` with any name you like, and the `url` with your server's address.
5. Choose **File → Save**. Do not rename the file.
6. Restart the service: press the **Windows key**, type `services.msc`, press **Enter**, find **Net_Monit_V107** in the list, right-click it and choose **Restart**.
7. Open the **Speed Test** page and click **Test WAN Speed**. The status line should now show your server's name and its round-trip time, and the **Target** column in the log shows it too.

**Steps on Linux**

1. Open the file: `sudo nano <install folder>/config.yaml` (the install folder is where you ran `setup.sh`).
2. Remove the `#` and one space from the start of the `speedtest:` lines shown above, change the name and address, save (Ctrl+O, Enter) and exit (Ctrl+X).
3. Restart: `sudo systemctl restart netmonit-v107`.

**Good to know**

- You can list several servers; Net-monit tries them in the order listed, and uses Cloudflare if none of them answers. A result always says which one it used.
- The file uses **spaces, never tabs**. If the service will not start after an edit, a tab or a missing space is the usual cause — the log file in the install folder's `logs/` folder names the line.
- `engine: builtin` (under `speedtest:`) tells Net-monit to skip the optional speedtest-cli library and always use its own test. The default, `auto`, tries speedtest-cli first and falls back to the built-in test.

## Upgrading to V10.7

If you're upgrading an existing V8.8, V10.0, V10.1, V10.2, V10.3, V10.4, V10.5, **or** V10.6 install rather than doing a fresh install, the steps are the same either way — only which old service/port/directory you're moving from changes.

1. **Your existing data is safe.** No database columns were removed or renamed this release. Devices, alert history, and settings all carry over.
2. Because the port and service name change with every release (5088 → 50100 → 50101 → 50102 → 50103 → 50104 → 50105 → 50106 → 50107; `Net_Monit_V88` → `Net_Monit_V100` → `Net_Monit_V101` → `Net_Monit_V102` → `Net_Monit_V103` → `Net_Monit_V104` → `Net_Monit_V105` → `Net_Monit_V106` → `Net_Monit_V107`), V10.7 installs **side-by-side** with whatever you had before rather than replacing it in place — the Windows/Linux installers will stop and remove the *old* service as part of installing the new one (see step 4 of the Windows section above), but the install directories are different (`C:\NetMonit-V8.8`, `C:\NetMonit-V10.0`, `C:\NetMonit-V10.1`, `C:\NetMonit-V10.2`, `C:\NetMonit-V10.3`, `C:\NetMonit-V10.4`, `C:\NetMonit-V10.5`, or `C:\NetMonit-V10.6`, vs. `C:\NetMonit-V10.7`), so keep your old install directory around until you've confirmed V10.7 is working, then remove it manually.
3. **Copy your `data/monitor.db` file** from the old install directory into the new one before first starting the V10.7 service, if you want to carry over devices, alert history, and settings. Alternatively, use the **Admin Panel → Backup & Restore** export/import feature from your old install before upgrading, and restore it once V10.7 is up — this is the recommended path. If you added a `speedtest:` section to `config.yaml`, copy those lines across too.
4. Update any firewall rules that reference your old port (5088, 50100, 50101, 50102, 50103, 50104, 50105, or 50106) to also allow 50107.
5. If you're coming from V8.8 specifically: your admin account's access token upgrades automatically to a stronger storage format (PBKDF2, not the older plain SHA-256) the next time that account successfully logs in — nothing you need to do, it happens transparently on sign-in. If you're already on V10.0, V10.1, V10.2, V10.3, V10.4, V10.5, or V10.6, this already happened.
6. **Check you are really on the new version.** After installing, the browser tab title and the About page must say **V10.7**, and the address must end in **:50107**. Every version keeps its own port, so an old bookmark (for example one ending in `:50106`) opens the *old* service, not the one you just installed. Also, Python does not pick up changed files while a service is running — if you ever copy new files over an existing install by hand, restart the service afterwards.
7. **What V10.7 changes**
   - **WAN speed test accuracy (fixes a V10.6 problem).** V10.6 could report a much lower speed than the connection really had — the slower the line, the bigger the shortfall — and a short test could run far longer than it should. Fixed: each step now ends on time and measures only while data is flowing. Upload is now counted at the receiving end (the old way over-read on slow lines). A step that cannot be measured now shows "--" instead of a made-up 0.
   - **The test tells you what it measured against.** The status line and a new **Target** column show the server and the round-trip time (for Cloudflare, which data centre answered). "Test WAN Speed" measures the route to that server, so on some providers it reads lower than speedtest.net, which tests against a server inside the provider. To measure against a nearer server, see *Optional: make the WAN speed test measure against a nearby server*, above.
   - **A new gauge.** The needle now follows the live speed through download (**green**), drops back, and follows upload (**purple**), with a coloured arc behind it. The scale is non-linear (0–1000) like speedtest.net's, so slow lines are readable too. The panel says **Showing: WAN** (or **Your PC**), and the log's Source badges read **WAN** and **PC**.
   - **PC speed test.** Upload is counted the same accurate way, latency is the typical (median) round trip, the ISP name is now filled in, and a direction that failed is stored as unknown rather than 0.
   - **Network Scan now shows TCP *and* UDP.** Every open port is labelled with its type (`22/tcp` in blue, `161/udp` in orange). A new **Check UDP ports too** option sends small standard requests (DNS, TFTP, NTP, NetBIOS, SNMP "public", UPnP, mDNS) and lists a UDP port only when the device *answers*. You can filter the results by port number, service name, `tcp` or `udp`.
   - **Safer display.** Host names, MAC/vendor names and other text discovered on your network are now shown as plain text, so a hostile device name cannot inject code into the page.

   If you don't use the Speed Test or Network Scan pages, V10.7 changes nothing else about how you use the product.

## Uninstalling

- **Windows:** run `Uninstall.bat` as Administrator (stops and removes the `Net_Monit_V107` service, offers to delete the install directory and data).
- **Linux:** run `scripts/linux/uninstall.sh` as root (stops, disables, and removes the systemd unit; offers to delete `/opt/netmonit-v107`).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Browser can't reach `http://localhost:50107` | Service isn't running — check `sc query Net_Monit_V107` (Windows) or `systemctl status netmonit-v107` (Linux). Also confirm nothing else is using port 50107. |
| Installer says Python not found (Windows) | Install Python 3.10+ from python.org and re-run `Setup.bat`. |
| Service starts then immediately stops | Check the log file in the install directory's `logs/` folder for the actual startup error — usually a missing pip dependency or a `config.yaml` syntax error. |
| Alert emails never arrive | Check Settings → SMTP is configured and saved, and that the host machine can reach your SMTP server on its configured port (some networks block outbound 25/587 by default). |
| SMS/call alerts never arrive | Check Settings → SMS & Call Alerts — use the "Send test" button there first; it surfaces the gateway's raw HTTP error, which is almost always more specific than "it didn't work." |
| "Test Your PC Speed" speed test fails but "Test WAN Speed" works fine | The end user's own network (not the server's) is blocking outbound HTTPS to `speed.cloudflare.com` — check their firewall/proxy/ad-blocker. This is expected behavior, not a bug: the two buttons test two different network paths. |
| Speed test "Hostname" column is blank | Expected on networks without reverse DNS configured for internal IPs (common on home/small-office networks, less common on a Windows AD domain) — the local IP is still shown even when the hostname can't be resolved. |
| Network Scan finds devices but MAC/vendor is blank for some | This is expected for devices Net-monit hasn't yet exchanged any traffic with (their entry isn't in this machine's ARP table yet) — re-running the scan after those devices have been contacted once usually fills it in. See the Admin Guide for more detail. |
| WAN speed is much lower than speedtest.net shows | "Test WAN Speed" measures to the server named in the status line (Cloudflare by default), not to a server inside your internet provider, and some providers route to Cloudflare more slowly than to their own network. Check the **Target** and round-trip time in the log; to measure against a nearer server, see *Optional: make the WAN speed test measure against a nearby server*. |
| Network Scan shows no UDP ports for a device | A UDP port is listed only when the device answers a request for that service (DNS, TFTP, NTP, NetBIOS, SNMP with community `public`, UPnP, mDNS). A silent device can still run UDP services — firewalls often drop these probes. The expanded row lists exactly which UDP ports were checked. |

For anything else, see the Admin Guide (day-to-day operation) or the User Guide (end-user features), both in this same `docs/` folder.
