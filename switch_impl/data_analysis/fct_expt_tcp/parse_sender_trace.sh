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
    cecho "YELLOW" "Usage: $0 <sender trace pcap file>"
    exit 1
fi


pcap_file=$1
outfile=${pcap_file%.*}".csv"

cecho "YELLOW" "Parsing sender trace from $pcap_file to $outfile"

tshark -r $pcap_file -t r -Tfields -e frame.number -e _ws.col.Time -e ip.src -e ip.dst -e tcp.srcport -e tcp.dstport -e tcp.hdr_len -e tcp.len -e tcp.seq -e tcp.ack -e tcp.flags.ack -e tcp.flags.push -e tcp.flags.reset -e tcp.flags.syn -e tcp.flags.fin -e tcp.seq_raw -e tcp.options.sack_le -e tcp.options.sack_re -e tcp.flags.cwr -E header=y -E separator=/t > $outfile

