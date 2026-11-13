#!/bin/sh
# Demo setup on the Pi, one command:  sudo sfw-demo <legit-ip> [rollback-minutes]
#
#   <legit-ip>          the laptop's address on the current network (marked as a known IP)
#   rollback-minutes    the rules remove themselves after this long (default 60), a safety net
#
# 1. queues the rollback, 2. clears the test data and marks the legit IP known,
# 3. loads the firewall rules, 4. restarts knockd so it binds the current address.
# Tailscale (the admin way in) is never filtered by the rules.
set -eu

DIR=/opt/smart-firewall
PY="$DIR/.venv/bin/python"
DB=/var/lib/sfw/state.db

[ "$(id -u)" -eq 0 ] || { echo "run it with sudo" >&2; exit 2; }
ip="${1:-}"
mins="${2:-60}"
[ -n "$ip" ] || { echo "usage: sudo sfw-demo <legit-ip> [rollback-minutes]" >&2; exit 2; }
"$PY" -c "import ipaddress,sys; ipaddress.IPv4Address(sys.argv[1])" "$ip" 2>/dev/null \
    || { echo "not an IPv4 address: $ip" >&2; exit 2; }
case "$mins" in ''|*[!0-9]*) echo "rollback minutes must be a number" >&2; exit 2;; esac

# Earlier rollbacks (queued by root) would remove the rules in the middle of the
# demo, so drop them first. Only root's jobs, nobody else's.
atq | awk '$NF == "root" { print $1 }' | xargs -r atrm

# Safety net first: if anything below goes wrong, the rules still go away.
echo '/usr/sbin/nft delete table inet sfw' | at now + "$mins" minutes 2>/dev/null

# Same tables as the manual reset. "meta" is kept.
sudo -u smart-firewall "$PY" -c "
import sqlite3, sys, time
d = sqlite3.connect('$DB')
for t in ('knocks', 'decisions', 'hard_flags', 'known_ips'):
    d.execute('delete from ' + t)
d.execute('insert into known_ips values (?, ?)', (sys.argv[1], time.time()))
d.commit()
" "$ip"

/usr/sbin/nft -f "$DIR/gateway/sfw.nft"
systemctl restart sfw-knockd
systemctl start sfw-dash
sleep 2

echo
systemctl is-active sfw-knockd sfw-dash
echo "ready. legit ip: $ip"
echo "pi address(es): $(hostname -I)"
echo "rules remove themselves in $mins minutes (or: sudo nft delete table inet sfw)"
