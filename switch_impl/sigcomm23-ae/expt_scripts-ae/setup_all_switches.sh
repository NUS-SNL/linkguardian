#!/bin/bash

my_dir="$(dirname "$0")"

source $my_dir/common/bash_common.sh

LINK_SPEEDS_CHECK_SCRIPT=/home/sigcomm23ae/linkguardian/switch_impl/sigcomm23-ae/expt_scripts-ae/common/check_link_speeds.py

linkspeedarg=""

if [ $# -eq 0 ]; then
    linkspeedarg="100G"
elif [ $# -eq 1 ]; then
    if [ $1 == "10G" ]; then
        linkspeedarg=$1
    else
        echo "Invalid command line option provided: $1"
        exit 1
    fi
else
    echo "More than one command line option provided"
fi

switchd_running=0
cecho "YELLOW" "Checking that switchd is not running on the switches..."
tofino1aSwitchd=`ssh tofino1a-ae "pgrep bf_switchd"`
tofino1cSwitchd=`ssh tofino1c-ae "pgrep bf_switchd"`
p4campusSwitchd=`ssh p4campus-proc1-ae "pgrep bf_switchd"`

if [ -z "$tofino1aSwitchd" ]; then
    cecho "GREEN" "Switchd is not running on tofino1a"
else
    cecho "RED" "Switchd is running on tofino1a"
    switchd_running=1
fi

if [ -z "$tofino1cSwitchd" ]; then
    cecho "GREEN" "Switchd is not running on tofino1c"
else
    cecho "RED" "Switchd is running on tofino1c"
    switchd_running=1
fi

if [ -z "$p4campusSwitchd" ]; then
    cecho "GREEN" "Switchd is not running on p4campus-proc1"
else
    cecho "RED" "Switchd is running on p4campus-proc1"
    switchd_running=1
fi

if [ $switchd_running -eq 1 ]; then
    echo "Please run teardown_all_switches.sh before running this script"
    exit 1
fi

echo ""
if [ $linkspeedarg == "100G" ];then
    cecho "YELLOW" "Setting up the switches with 100G linkspeed"    
    link_speed=100
    file_ext=""
elif [ $linkspeedarg == "10G" ]; then
    cecho "YELLOW" "Setting up the switches with 10G linkspeed"
    link_speed=10
    file_ext="_10g"
fi

###############################################
# Start the driver on all the switches
###############################################
echo -n "Starting switchd on tofino1a (sender.p4)... "
# clear the screen and start the driver
ssh tofino1a-ae "tmux send-keys -t driver.0 C-l './run_switchd.sh -p sender' ENTER"
cecho "GREEN" "Done"

echo -n "Starting switchd on tofino1c (receiver.p4)... "
# clear the screen and start the driver
ssh tofino1c-ae "tmux send-keys -t driver.0 C-l './run_switchd.sh -p receiver$file_ext' ENTER"
cecho "GREEN" "Done"

echo -n "Starting switchd on p4campus-proc1 (topo.p4)... "
# clear the screen and start the driver
ssh p4campus-proc1-ae "tmux send-keys -t driver.0 C-l './run_switchd.sh -p topo' ENTER"
cecho "GREEN" "Done"

echo ""


###############################################
# Run the setup script all the switches
###############################################

echo -n "Setting up initial config on tofino1a (sender.p4)... "
# clear the screen and run the setup script
ssh tofino1a-ae "tmux send-keys -t bfrt.0 C-l './run_bfshell.sh -b ../linkguardian/switch_impl/system_impl/sender/setup-ae$file_ext.py -i' ENTER"
cecho "GREEN" "Done"

echo -n "Setting up initial config on tofino1c (receiver.p4)... "
# clear the screen and run the setup script
ssh tofino1c-ae "tmux send-keys -t bfrt.0 C-l './run_bfshell.sh -b ../linkguardian/switch_impl/system_impl/receiver/setup-ae$file_ext.py -i' ENTER"
cecho "GREEN" "Done"

echo -n "Setting up initial config on p4campus-proc1 (topo.p4)... "
# clear the screen and run the setup script
ssh p4campus-proc1-ae "tmux send-keys -t bfrt.0 C-l './run_bfshell.sh -b ../linkguardian/switch_impl/topo_impl/setup-ae$file_ext.py -i' ENTER"
cecho "GREEN" "Done"

echo ""
sleep=20
cecho "YELLOW" "Waiting $sleep seconds for the initial config to complete and the links to come UP"
for ((i=1; i<=$sleep; i++)); do
    echo -n "."
    sleep 1
done
echo ""


###############################################
# Check for correct link speeds
###############################################
echo ""
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


echo ""

###############################################
# Check connectivity via ping
###############################################

cecho "YELLOW" "Checking connectivity via ping..."

$my_dir/common/check_connectivity.sh

