#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f /etc/os-release ]]; then
  echo "This script expects Ubuntu 22.04." >&2
  exit 1
fi

. /etc/os-release
if [[ "${ID:-}" != "ubuntu" || "${VERSION_ID:-}" != "22.04" ]]; then
  echo "Expected Ubuntu 22.04, got ${PRETTY_NAME:-unknown}" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

echo "[1/7] Installing base packages..."
sudo apt update
sudo apt install -y \
  locales \
  software-properties-common \
  curl \
  git \
  make \
  python3-pip \
  python3-venv \
  ca-certificates \
  gnupg \
  lsb-release

echo "[2/7] Configuring locale..."
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

echo "[3/7] Enabling Ubuntu universe repository..."
sudo add-apt-repository universe -y

echo "[4/7] Adding official ROS 2 apt source..."
ROS_APT_SOURCE_VERSION="$({
  curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest \
  | grep -F 'tag_name' \
  | awk -F'"' '{print $4}';
} )"

curl -L -o /tmp/ros2-apt-source.deb \
  "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.${UBUNTU_CODENAME}_all.deb"

sudo dpkg -i /tmp/ros2-apt-source.deb

echo "[5/7] Updating apt metadata..."
sudo apt update

echo "[6/7] Installing ROS 2 Humble + Gazebo bridge packages..."
sudo apt install -y \
  ros-humble-desktop \
  ros-humble-ros-gz \
  ros-humble-teleop-twist-keyboard \
  ros-dev-tools

echo "[7/7] Configuring shell environment..."
if ! grep -q 'source /opt/ros/humble/setup.bash' "$HOME/.bashrc"; then
  echo 'source /opt/ros/humble/setup.bash' >> "$HOME/.bashrc"
fi
if ! grep -q 'export ROS_DOMAIN_ID=' "$HOME/.bashrc"; then
  echo 'export ROS_DOMAIN_ID=30' >> "$HOME/.bashrc"
fi
if ! grep -q 'export ROS_LOCALHOST_ONLY=' "$HOME/.bashrc"; then
  echo 'export ROS_LOCALHOST_ONLY=0' >> "$HOME/.bashrc"
fi

echo
echo "Done."
