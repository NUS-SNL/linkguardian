#!/bin/bash

cecho(){  # source: https://stackoverflow.com/a/53463162/2886168
    RED="\033[0;31m"
    GREEN="\033[0;32m"
    YELLOW="\033[0;33m"
    # ... ADD MORE COLORS
    NC="\033[0m" # No Color

    printf "${!1}${2} ${NC}\n"
}

# Check if expt name and number is passed as an argument
if [ $# -ne 1 ];then
    cecho "YELLOW" "Usage: $0 <affected_flows pcap file>"
    exit 1
fi


pcap_file=$1
outfile=${pcap_file%.*}".csv"

cecho "YELLOW" "Parsing affected flows from $pcap_file to $outfile"

tshark -r $pcap_file -t r -Tfields -e tcp.srcport -e _ws.col.Time -e eth.src -e ip.ttl -e tcp.flags.ack -e tcp.flags.push -e tcp.flags.syn -e tcp.flags.fin -e tcp.len -e tcp.seq_raw -E header=y -E separator=/t > $outfile
