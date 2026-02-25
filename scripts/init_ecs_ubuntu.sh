#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   sudo ./scripts/init_ecs_ubuntu.sh
#
# Purpose:
#   Bootstrap an Ubuntu ECS host with Docker Engine + Compose plugin
#   for VideoBling production deployment.

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Please run as root (or with sudo): sudo $0"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  git \
  gnupg \
  lsb-release

install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
fi
chmod a+r /etc/apt/keyrings/docker.gpg

ARCH="$(dpkg --print-architecture)"
CODENAME="$(. /etc/os-release && echo "${VERSION_CODENAME:-}")"
if [[ -z "$CODENAME" ]]; then
  CODENAME="$(lsb_release -cs)"
fi

cat >/etc/apt/sources.list.d/docker.list <<EOF
deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${CODENAME} stable
EOF

apt-get update
apt-get install -y --no-install-recommends \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

systemctl enable docker
systemctl restart docker

if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
  usermod -aG docker "${SUDO_USER}" || true
fi

echo
echo "Init complete:"
docker --version
docker compose version

if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
  echo
  echo "User '${SUDO_USER}' has been added to docker group."
  echo "Please re-login for group changes to take effect."
fi
