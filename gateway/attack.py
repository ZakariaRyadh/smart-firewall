"""Live attack demo for the lab. Run it on the attacker VM:

    python3 gateway/attack.py <scenario> <gateway-ip> [--source <ip>] [--seed N]

The attacker "has a valid password and knows the knock" but behaves in an
unusual way. The scenarios match sfw/attack_sim.py, replayed against the real
gateway:

    burst       20 knocks, 1-2 s apart        -> hard rule (rate_1min)
    volume      25 knocks, 5-15 s apart       -> hard rule (rate_5min / rate_1min)
    new_ip      one knock from a new address  -> the model (needs --source, see below)
    slow_known  one knock from the known IP   -> allowed. This is a known limit

For new_ip add an address to the attacker first, then pass it:
    sudo ip addr add 10.10.10.4/24 dev enp2s0
    python3 gateway/attack.py new_ip 10.10.10.2 --source 10.10.10.4

The knock ports come from ~/.config/sfw/knock.conf (the NORMAL line), the same
private file knock.sh uses. They are never in git and never printed.
Lab use only: the target and the source must be private addresses. The attacker
cannot see the gateway's decisions, look at the dashboard for those.
Standard library only, so it runs on the bare attacker VM.
"""
import argparse
import ipaddress
import os
import random
import socket
import sys
import time

DEFAULT_CONF = os.path.expanduser("~/.config/sfw/knock.conf")

# scenario: (number of knocks, (min gap, max gap) in seconds after each knock)
SCENARIOS = {
    "burst": (20, (1, 2)),
    "volume": (25, (5, 15)),
    "new_ip": (1, (0, 0)),
    "slow_known": (1, (0, 0)),
}


def load_ports(path):
    """The NORMAL line of knock.conf as a list of ports. Exits with a clear
    message if the file or the line is missing or still has placeholders."""
    try:
        with open(path) as f:
            lines = f.read().splitlines()
    except OSError:
        sys.exit(f"missing {path} (copy gateway/knock.conf.example and set your ports)")
    for line in lines:
        key, _, value = line.strip().partition("=")
        if key.strip() == "NORMAL":
            words = value.strip().strip('"').strip("'").split()
            break
    else:
        sys.exit(f"no NORMAL line in {path}")
    if not words:
        sys.exit(f"NORMAL is empty in {path}")
    ports = []
    for w in words:
        if not (w.isdigit() and 1 <= int(w) <= 65535):
            sys.exit(f"NORMAL in {path} must be port numbers, found {w!r}")
        ports.append(int(w))
    return ports


def private_ip(value):
    """Only literal private IPv4 addresses (and loopback). A guard so the
    script cannot be pointed at a machine we do not own by mistake."""
    try:
        ip = ipaddress.IPv4Address(value)
    except ValueError:
        sys.exit(f"{value!r} is not an IPv4 address (names are not accepted)")
    if not ip.is_private:
        sys.exit(f"{value} is not a private address, this tool is for the lab only")
    return str(ip)


def plan(name, rng):
    """Seconds to wait after each knock of the scenario."""
    if name not in SCENARIOS:
        sys.exit(f"unknown scenario {name!r}, choose from: {', '.join(SCENARIOS)}")
    count, (lo, hi) = SCENARIOS[name]
    return [rng.uniform(lo, hi) for _ in range(count)]


def knock(host, ports, source=None, timeout=0.3):
    """One SYN to each port, in order. The ports are closed, so nothing answers;
    the gateway only needs to see the packets. Errors never stop a knock."""
    for port in ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.settimeout(timeout)
            if source:
                s.bind((source, 0))
            s.connect_ex((host, port))
        except OSError:
            pass
        finally:
            s.close()


def probe_ssh(host, source=None, timeout=3.0):
    """Can the attacker reach the SSH port right now?"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(timeout)
        if source:
            s.bind((source, 0))
        return "open" if s.connect_ex((host, 22)) == 0 else "closed or blocked"
    except OSError:
        return "closed or blocked"
    finally:
        s.close()


def run(name, host, ports, rng, knock_fn, sleep_fn, probe_fn, out, source=None):
    gaps = plan(name, rng)
    out(f"attack {name} against {host}: {len(gaps)} knock(s)"
        + (f" from {source}" if source else ""))
    for i, gap in enumerate(gaps, 1):
        knock_fn(host, ports, source=source)
        out(f"  knock {i}/{len(gaps)} sent")
        if i < len(gaps):
            sleep_fn(gap)
    sleep_fn(4)                      # let the gateway finish deciding
    out(f"SSH port 22 from here: {probe_fn(host, source=source)}")
    out("Look at the dashboard for the gateway's decisions.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Live attack demo (lab only).")
    ap.add_argument("scenario", choices=sorted(SCENARIOS))
    ap.add_argument("host", help="gateway IP (private address)")
    ap.add_argument("--source", help="send from this local address (private)")
    ap.add_argument("--config", default=DEFAULT_CONF)
    ap.add_argument("--seed", type=int, help="same seed, same timing")
    args = ap.parse_args(argv)

    host = private_ip(args.host)
    source = private_ip(args.source) if args.source else None
    ports = load_ports(args.config)
    try:
        run(args.scenario, host, ports, random.Random(args.seed), knock,
            time.sleep, probe_ssh, print, source=source)
    except KeyboardInterrupt:
        print("stopped")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
