#!/bin/bash

mydir=$(dirname $0)

cecho(){  # source: https://stackoverflow.com/a/53463162/2886168
    RED="\033[0;31m"
    GREEN="\033[0;32m"
    YELLOW="\033[0;33m"
    # ... ADD MORE COLORS
    NC="\033[0m" # No Color

    printf "${!1}${2} ${NC}\n"
}

# Check if expt name and number is passed as an argument
if [ $# -ne 2 ];then
    cecho "YELLOW" "Usage: $0 <dst dir> <flow_size_B>"
    exit 1
fi

shopt -s nullglob

dst_dir=$1
flow_size=$2

file_list=($dst_dir/${flow_size}B_sender*.pcap)

PARSER_SCRIPT=$mydir/parse_sender_trace.sh

num_runs=${#file_list[@]}

cecho "YELLOW" "Number of runs found: $num_runs"

# printf '%s\n' "${file_list[@]}"

# Parallelizing the parsing process
while read a b c d e;do 
    ${PARSER_SCRIPT} $a &
    ${PARSER_SCRIPT} $b &
    ${PARSER_SCRIPT} $c &
    ${PARSER_SCRIPT} $d &
    ${PARSER_SCRIPT} $e &
    wait; 
done < <(echo "${file_list[@]}" | xargs -n5)

# for file in "${file_list[@]}";do
#     ${PARSER_SCRIPT} $file
# done

cecho "YELLOW" "Total runs parsed: $num_runs"

