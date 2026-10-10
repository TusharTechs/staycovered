#!/usr/bin/env bash
# Deploy StayCovered to a Linux VM (e.g. Nebius AI Cloud) over SSH.
#   scripts/deploy_vm.sh <user>@<public-ip> [ssh-key]
# First run installs Docker + Caddy (automatic HTTPS at https://<ip-with-dashes>.sslip.io). Later runs just redeploy.
# API keys are copied from the local .env to the server with 600 permissions; they never enter the image or git.
set -euo pipefail

TARGET="${1:?usage: deploy_vm.sh user@ip [ssh-key]}"
KEY="${2:-$HOME/.ssh/staycovered_nebius}"
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IP="${TARGET#*@}"
HOST="${IP//./-}.sslip.io"

echo "==> syncing project to $TARGET"
rsync -az --delete -e "$SSH" \
  --exclude .git --exclude .env --exclude .venv --exclude 'web/node_modules' --exclude 'web/dist' \
  --exclude research --exclude 'data/runtime' --exclude '__pycache__' --exclude PLAN.md \
  "$ROOT/" "$TARGET:~/staycovered/"
scp -i "$KEY" -q "$ROOT/.env" "$TARGET:~/staycovered/.env"

$SSH "$TARGET" HOST="$HOST" bash -s <<'REMOTE'
set -euo pipefail
chmod 600 ~/staycovered/.env
if ! command -v docker >/dev/null; then
  echo "==> installing docker"
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi
if ! command -v caddy >/dev/null; then
  echo "==> installing caddy"
  sudo apt-get update -qq && sudo apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update -qq && sudo apt-get install -y -qq caddy
fi
echo "$HOST {
  encode gzip
  reverse_proxy 127.0.0.1:8000
}" | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo systemctl reload caddy || sudo systemctl restart caddy

cd ~/staycovered
echo "==> building image"
sudo docker build -q -t staycovered .
sudo docker rm -f staycovered >/dev/null 2>&1 || true
sudo docker volume create staycovered-runtime >/dev/null
sudo docker run -d --name staycovered --restart always --env-file .env \
  -v staycovered-runtime:/app/data/runtime -p 127.0.0.1:8000:8000 staycovered >/dev/null
sleep 3
curl -fsS 127.0.0.1:8000/api/health && echo
echo "==> live at https://$HOST"
REMOTE
