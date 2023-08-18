#!/bin/bash


if [ $# -ne 2 ]; then
    echo "Usage: $0 <run file with format <ts, cells>> <num_pkts>"
    exit
fi

filepath=$1
last_line=$(($2 + 1))

# Get first pkt ts
# tail -n +2 1000pkts_run1.dat | head -n +1 | cut -f1

# Get last pkt ts
# tail -n +1001 1000pkts_run1.dat | cut -f1

start_time=$(tail -n +2 $filepath | head -n +1 | cut -f1)
end_time=$(tail -n +${last_line} $filepath | cut -f1)

echo -e "${start_time}\t${end_time}"


