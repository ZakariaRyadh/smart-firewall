#!/usr/bin/env bash
# Client for the user's laptop: knock, then SSH. If the gateway stays closed
# (the model was unsure, "harder knock"), do the longer knock and try again.
# The user never has to know which case they are in.
#
#   knock.sh <gateway-ip> [ssh-user]
#
# Ports live in a private config file, never in git:
#   ~/.config/sfw/knock.conf   (copy gateway/knock.conf.example, set your ports)
#   SFW_KNOCK_CONF=/other/path overrides the location.
set -u

host="${1:-}"
user="${2:-$USER}"
[ -n "$host" ] || { echo "usage: $0 <gateway-ip> [ssh-user]" >&2; exit 2; }

conf="${SFW_KNOCK_CONF:-$HOME/.config/sfw/knock.conf}"
[ -r "$conf" ] || { echo "missing $conf (copy gateway/knock.conf.example)" >&2; exit 2; }
# The file is the user's own and holds shell variables: NORMAL, HARD, WAIT, TIMEOUT.
# shellcheck disable=SC1090
. "$conf"
: "${NORMAL:?set NORMAL in $conf}" "${HARD:?set HARD in $conf}"
WAIT="${WAIT:-4}"          # seconds for the gateway to score the knock (Python starts each time)
TIMEOUT="${TIMEOUT:-6}"    # seconds before SSH gives up on a closed door

knock() {                  # knock <port>...
    for p in "$@"; do
        timeout 1 bash -c "echo > /dev/tcp/$host/$p" 2>/dev/null
    done
}

# Try SSH. Returns 99 when the door is closed (connect timed out), so we can
# tell it apart from a normal exit or a wrong password.
try_ssh() {
    local start=$SECONDS rc
    ssh -o ConnectTimeout="$TIMEOUT" "$user@$host"
    rc=$?
    if [ "$rc" -eq 255 ] && [ $((SECONDS - start)) -ge $((TIMEOUT - 1)) ]; then
        return 99
    fi
    return "$rc"
}

# shellcheck disable=SC2086   # the port lists are meant to split on spaces
knock $NORMAL
sleep "$WAIT"
try_ssh; rc=$?
[ "$rc" -ne 99 ] && exit "$rc"

echo "Door closed, trying the longer knock..." >&2
# shellcheck disable=SC2086
knock $HARD
sleep "$WAIT"
try_ssh; rc=$?
if [ "$rc" -eq 99 ]; then
    echo "No access: blocked, wrong knock, or the longer knock is not allowed for this address." >&2
    exit 1
fi
exit "$rc"
