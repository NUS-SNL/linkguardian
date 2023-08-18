#!/bin/bash

if [ $# -ne 1 ];then
	echo "Usage: $0 <ondemand/performance>"
	exit 1
fi

mode=$1

if [ "$mode" = "ondemand"  ]; then
	echo "Switching to ondemand mode..."
	sudo sh -c "echo 'GOVERNOR=\"ondemand\"' > /etc/default/cpufrequtils"
	sudo systemctl restart cpufrequtils.service
elif [ "$mode" = "performance" ]; then
	echo "Switching to performance mode..."
	sudo sh -c "echo 'GOVERNOR=\"performance\"' > /etc/default/cpufrequtils"
	sudo systemctl restart cpufrequtils.service
else
	echo "Invalid mode: ${mode}"
	exit 1
fi


