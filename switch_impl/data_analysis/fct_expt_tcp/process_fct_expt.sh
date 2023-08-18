#!/bin/bash

# BASE_DIR=/home/raj/workspace/linkradar/data-analysis/motivation/fct
mydir=$(dirname $0)
BASE_DIR=$mydir

cecho(){  # source: https://stackoverflow.com/a/53463162/2886168
    RED="\033[0;31m"
    GREEN="\033[0;32m"
    YELLOW="\033[0;33m"
    # ... ADD MORE COLORS
    NC="\033[0m" # No Color

    printf "${!1}${2} ${NC}\n"
}

# Check if the script is being run on jarvis
# hostname=`hostname`
# if [[ "$hostname" != "jarvis" ]];then
#     cecho "RED" "ERROR: This script needs to run on jarvis"
#     exit 1
# fi

# Check if expt name and number is passed as an argument
if [ $# -lt 4 ];then
    cecho "YELLOW" "Usage: $0 <target dir with pcaps> <flow size in Bytes> <expt_type (motivation/evaluation)> <MTU size: 1068/1500> [--no-affected]"
    cecho "YELLOW" "expt_type:"
    echo "If you don't have affected flows trace, just used expt_type as 'motivation'"
    exit 1
fi

TARGET_DIR=$1
flow_size=$2
expt_type=$3
mtu=$4
no_affected=0

if [ $# -eq 5 ];then
    if [ "$5" == "--no-affected" ];then
        no_affected=1
    else
        echo "Invalid option $4"
        cecho "YELLOW" "Usage: $0 <target dir with pcaps> <flow size in Bytes> <expt_type (motivation/evaluation)> [--no-affected]"
        cecho "YELLOW" "expt_type:"
        echo "If you don't have affected flows trace, just used expt_type as 'motivation'"
        exit 1
    fi
fi

# Check MTU size
if [ "$mtu" != "1500" ] && [ "$mtu" != "1068" ]; then
    cecho "YELLOW" "ERROR: The specified MTU size \"$mtu\" is incorrect. Specify either 1500 or 1068"
    exit 1
fi


cecho "YELLOW" "Processing expt: $TARGET_DIR ${flow_size}B"
# cecho "YELLOW" "Expt Type: $expt_type"

if [ $no_affected -eq 0 ]; then
    echo "#####################################################"
    cecho "YELLOW" "Parsing all affected flows"
    echo "#####################################################"
    # Parse the affected flows traces
    $BASE_DIR/parse_all_affected_flows.sh $TARGET_DIR ${flow_size}
fi

echo "#####################################################"
cecho "YELLOW" "Parsing all sender traces"
echo "#####################################################"
# Parse the sender-side traces
$BASE_DIR/parse_all_sender_traces.sh $TARGET_DIR ${flow_size}

if [ $no_affected -eq 0 ]; then
    echo "#####################################################"
    cecho "YELLOW" "Processing all affected flows"
    echo "#####################################################"
    # Process affected flows traces
    $BASE_DIR/process_all_affected_flows.sh $TARGET_DIR ${flow_size}
fi


echo "#####################################################"
cecho "YELLOW" "Processing all sender traces"
echo "#####################################################"
# # Process the sender-side trace
$BASE_DIR/process_all_sender_traces.sh $TARGET_DIR ${flow_size} $expt_type $mtu $no_affected --silent | tee $TARGET_DIR/sender_processing.log

