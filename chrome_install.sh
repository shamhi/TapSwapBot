#!/bin/bash

if ! command -v google-chrome &> /dev/null
then
    echo "Installing Google Chrome"

    sudo apt update
    sudo apt install -y wget curl gnupg
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    sudo dpkg -i google-chrome-stable_current_amd64.deb
    sudo apt install -f -y

    echo "Google Chrome installed successfully"
else
    echo "Google Chrome already installed"
fi
