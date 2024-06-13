#!/bin/bash

# Update package list and install prerequisites
echo "Updating package list and installing prerequisites..."
sudo apt update
sudo apt install -y software-properties-common

# Add Mozilla Team PPA
echo "Adding Mozilla Team PPA..."
sudo add-apt-repository -y ppa:mozillateam/ppa

# Set package pinning preferences
echo "Setting package pinning preferences..."
sudo tee /etc/apt/preferences.d/mozilla-firefox <<EOF
Package: *
Pin: release o=LP-PPA-mozillateam
Pin-Priority: 1001
EOF

# Configure unattended upgrades for Mozilla Team PPA
echo "Configuring unattended upgrades for Mozilla Team PPA..."
sudo tee /etc/apt/apt.conf.d/51unattended-upgrades-firefox <<EOF
Unattended-Upgrade::Allowed-Origins:: "LP-PPA-mozillateam:\${distro_codename}";
EOF

# Update package list again and install Firefox
echo "Updating package list and installing Firefox..."
sudo apt update
sudo apt install -y firefox

echo "Installation complete!"
