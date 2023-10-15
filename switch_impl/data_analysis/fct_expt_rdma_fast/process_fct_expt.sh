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

if [ $# -ne 1 ]; then
    cecho "YELLOW" "Usage: $0 <target expt log file>"
    exit 1
fi

expt_log_file=$1
data_file=${expt_log_file%.*}".dat"  # remove the extension and add .dat

# Export just the FCT values while converting to microseconds
tail -n +2 $expt_log_file | cut -d',' -f2 | awk '{printf("%.3f\n",$1/1000)}'> $data_file
