#!/bin/bash

if pgrep -f "PalServer-Linux-Shipping" > /dev/null
then 
	echo "RUNNING" 
else 
	echo "STOPPED" 
fi
