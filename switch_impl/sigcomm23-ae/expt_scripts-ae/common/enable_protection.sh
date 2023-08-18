#!/bin/bash

mydir=$(dirname $0)
source $mydir/bash_common.sh

if [ $# -ne 1 ];then
    cecho "YELLOW" "Usage: $0 <1/0 blocking or non-blocking>"
    exit 1
fi

mode=$1

ssh tofino1a-ae "tmux send-keys -t bfrt.0 C-l 'enable_protection(32, $mode)' ENTER 'check_sender_state()' ENTER"
