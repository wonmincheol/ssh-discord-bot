#!/bin/bash

if ! pgrep -f "PalServer-Linux-Shipping" >/dev/null
then
    echo "ALREADY_STOPPED"
    exit 0
fi

if sudo -u steam pkill -f "PalServer-Linux-Shipping"
then
    echo "STOPPED"
else
    echo "FAILED"
    exit 1
fi
