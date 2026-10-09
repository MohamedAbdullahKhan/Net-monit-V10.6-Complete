#!/usr/bin/env bash
# Net-monit V10.7 Linux Uninstaller
set -euo pipefail
[[ $EUID -ne 0 ]] && echo "Run as root: sudo bash uninstall.sh" && exit 1
SVC="${1:-netmonit-v107}"
echo "Stopping and removing Net-monit V10.7 ($SVC)..."
systemctl stop    "$SVC" 2>/dev/null || true
systemctl disable "$SVC" 2>/dev/null || true
rm -f "/etc/systemd/system/${SVC}.service"
systemctl daemon-reload
echo "Service removed. Data preserved at: /opt/netmonit-v107/data/"
echo "To remove all files: rm -rf /opt/netmonit-v107"
