#!/bin/bash

mydir=`dirname $0`
source $mydir/bash_common.sh

if [ $# -ne 1 ]; then
    cecho "YELLOW" "Usage: $0 <link_speed: 10/100>"
    exit 1
fi

link_speed=$1

LINK_SPEEDS_CHECK_SCRIPT=/home/sigcomm23ae/linkguardian/switch_impl/sigcomm23-ae/expt_scripts-ae/common/check_link_speeds.py

if [ $link_speed -ne 10 ] && [ $link_speed -ne 100 ] && [ $link_speed -ne 25 ]; then
    cecho "YELLOW" "Link speed must be 10, 25 or 100"
    cecho "YELLOW" "Usage: $0 <link_speed: 10/25/100>"
    exit 1
fi


cecho "GREEN" "Changing link speeds to $link_speed Gbps"

ssh tofino1a-ae "tmux send-keys -t bfrt.0 C-l 'change_link_speeds($link_speed)' ENTER"
ssh tofino1c-ae "tmux send-keys -t bfrt.0 C-l 'change_link_speeds($link_speed)' ENTER"
ssh p4campus-proc1-ae "tmux send-keys -t bfrt.0 C-l 'change_link_speeds($link_speed)' ENTER"

cecho "YELLOW" "Waiting 5s for all links to come up"
sleep 5

cecho "YELLOW" "Checking if all links are up"

all_links_up=0

while [ $all_links_up -eq 0 ]; do
    all_links_up=1

    link_up_proc1=`ssh p4campus-proc1-ae "env SDE_INSTALL=/home/sigcomm23ae/bf-sde-9.11.1/install $LINK_SPEEDS_CHECK_SCRIPT $link_speed 2> /dev/null"`
    
    link_up_tof1a=`ssh tofino1a-ae "env SDE_INSTALL=/home/sigcomm23ae/bf-sde-9.10.0/install $LINK_SPEEDS_CHECK_SCRIPT $link_speed 2> /dev/null"`
    
    link_up_tof1c=`ssh tofino1c-ae "env SDE_INSTALL=/home/sigcomm23ae/bf-sde-9.9.0/install $LINK_SPEEDS_CHECK_SCRIPT $link_speed 2> /dev/null"`

    if [ $link_up_proc1 -eq 0 ]; then
        cecho "RED" "Links on p4campus-proc1 are still down"
        all_links_up=0
    fi

    if [ $link_up_tof1a -eq 0 ]; then
        cecho "RED" "Links on tofino1a are still down"
        all_links_up=0
    fi

    if [ $link_up_tof1c -eq 0 ]; then
        cecho "RED" "Links on tofino1c are still down"
        all_links_up=0
    fi

    if [ $all_links_up -eq 0 ]; then
        cecho "YELLOW" "Waiting 5s more for all links to come up"
        sleep 5
    fi
done

cecho "GREEN" "All links are up with link speed $link_speed Gbps"




