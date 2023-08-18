#!/bin/bash

if [ $# -ne 1 ];then
	echo "Usage: $0 <enable/disable>"
	exit 1
fi

mode=$1

if [ "$mode" = "enable"  ]; then
	echo "Enabling performance mode..."
	sudo cpupower idle-set -d 3
	sudo cpupower idle-set -d 2
	sudo cpupower idle-set -d 1
elif [ "$mode" = "disable" ]; then
	echo "Disabling performance mode..."
	sudo cpupower idle-set -E
else
	echo "Invalid command: ${mode}"
	exit 1
fi


