#!/bin/bash

if pgrep -f "PalServer-Linux-Shipping" >/dev/null
then
    echo "ALREADY_RUNNING"
    exit 0
fi

sudo -u steam /data/palworld/PalServer.sh >/dev/null 2>&1 &

echo "STARTED"
