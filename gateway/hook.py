"""Gateway hook: knockd runs this once per correct knock.

    python -m gateway.hook <ip>           normal knock: score it, then allow / block / flag
    python -m gateway.hook --hard <ip>    longer knock: opens only for a flagged IP

In knockd.conf, one door per command (see gateway/knockd.conf.example).
Paths come from the environment (same names as the dashboard):
    SFW_DB     state database   (default /var/lib/sfw/state.db)
    SFW_MODEL  model bundle     (default models/model.joblib)

Fail closed: if anything goes wrong nothing is opened, the error is logged
and the exit code is 1. Wrong knocks never reach this hook, knockd only
runs its command on a full correct sequence.
"""
import ipaddress
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from sfw.decide import ALLOW, Decision, decide
from sfw.rules import BLOCK, HARDER
from sfw.state import (clear_hard_flag, connect, flag_hard, hard_flag_active,
                       live_features, log_decision, mark_known, recent_knocks,
                       record_knock)

ROOT = Path(__file__).resolve().parents[1]
NFT = "/usr/sbin/nft"
TABLE = ("inet", "sfw")
log = logging.getLogger("sfw.hook")


def valid_ipv4(ip):
    """Return the address as a string, or raise ValueError. IPv4 only, because
    the nft sets are ipv4_addr. Stops anything odd from reaching nft."""
    return str(ipaddress.IPv4Address(ip))


class Nft:
    """The real firewall. Arguments are a fixed list, never a shell string."""

    def _add(self, set_name, ip):
        ip = valid_ipv4(ip)
        subprocess.run([NFT, "add", "element", *TABLE, set_name, f"{{ {ip} }}"],
                       check=True, capture_output=True, timeout=5)

    def allow(self, ip):
        self._add("knocked", ip)   # open SSH, entry expires (timeout in sfw.nft)

    def block(self, ip):
        self._add("blocked", ip)   # dropped first in the chain, expires too


def handle_knock(db, bundle, ip, now, fw):
    """One correct knock. Order follows sfw/state.py. Returns the Decision.

    The decision is logged before the firewall is touched, so the dashboard
    shows it even if nft fails. If nft fails the error goes up, the IP is not
    marked known, and SSH stays closed.
    """
    ip = valid_ipv4(ip)
    feats = live_features(db, ip, now)         # before recording this knock
    record_knock(db, ip, now, ok=True)
    knocks = recent_knocks(db, ip, now)
    d = decide(bundle, feats, knocks, now)
    log_decision(db, ip, now, d, feats)
    if d.action == ALLOW:
        fw.allow(ip)
        mark_known(db, ip, now)
        clear_hard_flag(db, ip)
    elif d.action == BLOCK:
        fw.block(ip)
        clear_hard_flag(db, ip)        # a blocked IP must not get in through the hard door
    elif d.action == HARDER:
        flag_hard(db, ip, now)         # nothing opens, the longer knock can now work
    return d


def handle_hard_knock(db, ip, now, fw):
    """The longer knock. Opens SSH only for an IP flagged by a "harder knock",
    once, within HARD_WINDOW. Anyone else is ignored (no log, no reply), so a
    stranger who guesses the sequence learns nothing. Returns the Decision, or
    None when ignored. If nft fails the flag stays, so the user can retry.

    It does not make the IP known and does not count as a normal knock.
    """
    ip = valid_ipv4(ip)
    if not hard_flag_active(db, ip, now):
        return None
    fw.allow(ip)
    clear_hard_flag(db, ip)
    d = Decision(ALLOW, "hard_knock")
    log_decision(db, ip, now, d)
    return d


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    logging.basicConfig(level=logging.INFO, format="sfw-hook %(levelname)s %(message)s")
    hard = "--hard" in argv
    args = [a for a in argv if a != "--hard"]
    if len(args) != 1 or len(argv) - len(args) > 1:
        log.error("usage: python -m gateway.hook [--hard] <ip>")
        return 2
    try:
        ip = valid_ipv4(args[0])
        db = connect(os.environ.get("SFW_DB", "/var/lib/sfw/state.db"))
        now = datetime.now().astimezone()
        if hard:                               # no model needed, keeps it fast
            d = handle_hard_knock(db, ip, now, Nft())
            log.info("%s -> %s", ip, f"{d.action} ({d.reason})" if d else "hard knock ignored")
            return 0
        import joblib                          # slow import, only when needed
        bundle = joblib.load(os.environ.get("SFW_MODEL", str(ROOT / "models" / "model.joblib")))
        d = handle_knock(db, bundle, ip, now, Nft())
        log.info("%s -> %s (%s)", ip, d.action, d.reason)
        return 0
    except Exception:
        log.exception("hook failed, nothing opened")
        return 1


if __name__ == "__main__":
    sys.exit(main())
