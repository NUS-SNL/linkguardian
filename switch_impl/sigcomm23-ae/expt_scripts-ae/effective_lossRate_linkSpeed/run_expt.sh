#!/bin/bash


my_dir="$(dirname "$0")"
source $my_dir/../common/bash_common.sh

if [ $# -ne 2 ];then
    cecho "YELLOW" "Usage: $0 'expt_name' <1/0 - blocking or non-blocking>"
    exit 1
fi

expt_name=$1

if [ "$2" = "1" ];then
    nb_mode=False
elif [ "$2" = "0" ]; then
    nb_mode=True
else
    cecho "RED" "Invalid mode: $2"
    exit 1
fi

cecho "YELLOW" "Starting expt '$expt_name' with nb_mode=$nb_mode ..."

ssh tofino1a-ae "tmux send-keys -t bfrt.0 C-l 'run_effective_lossRate_linkSpeed_expt(expt_name=\"$expt_name\", poll_buffs=True, num_pkts=NUMBER_100M, nb_mode=$nb_mode, rand_drop=True)' C-o ENTER"



# TODO: qualify the argument names
ssh tofino1a-ae "tmux send-keys -t bfrt.0 'copy_sw_data_effective_lossRate_linkSpeed_expt(\"$expt_name\", $nb_mode, \"lumos-ae\", \"/home/sigcomm23ae/linkguardian/switch_impl/sigcomm23-ae/expt_scripts-ae/effective_lossRate_linkSpeed\")' ENTER ENTER"

echo "Please check terminal tab 2 (bfrt tmux session on the sender sw) for status of the experiment"




