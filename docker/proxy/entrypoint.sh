#!/bin/sh
# Holds an outbound `ssh -D` SOCKS5 tunnel to a jump host that has direct
# internet access, so the bot/worker/api containers (which don't) can reach
# Telegram/OpenAI/social platforms through it. autossh restarts the tunnel
# automatically if it drops.
set -eu

: "${PROXY_SSH_HOST:?PROXY_SSH_HOST is required (jump host address)}"
: "${PROXY_SSH_USER:?PROXY_SSH_USER is required (jump host username)}"

PROXY_SSH_PORT="${PROXY_SSH_PORT:-22}"
SOCKS_PORT="${SOCKS_PORT:-1080}"
KEY_SRC="${PROXY_SSH_KEY_PATH:-/keys/id_ed25519}"

if [ ! -f "$KEY_SRC" ]; then
    echo "ERROR: SSH private key not found at $KEY_SRC (mount it as a volume)" >&2
    exit 1
fi

mkdir -p /root/.ssh
chmod 700 /root/.ssh
cp "$KEY_SRC" /root/.ssh/id_tunnel
chmod 600 /root/.ssh/id_tunnel

export AUTOSSH_GATETIME=0
export AUTOSSH_POLL=30

exec autossh -M 0 -N \
    -o "BatchMode=yes" \
    -o "StrictHostKeyChecking=no" \
    -o "UserKnownHostsFile=/dev/null" \
    -o "ServerAliveInterval=30" \
    -o "ServerAliveCountMax=3" \
    -o "ExitOnForwardFailure=yes" \
    -D "0.0.0.0:${SOCKS_PORT}" \
    -p "${PROXY_SSH_PORT}" \
    -i /root/.ssh/id_tunnel \
    "${PROXY_SSH_USER}@${PROXY_SSH_HOST}"
