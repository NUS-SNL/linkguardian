#!/bin/bash

my_dir="$(dirname "$0")"

source $my_dir/common/bash_common.sh

cecho "YELLOW" "Stopping switchd on tofino1a (sender.p4)"
ssh tofino1a-ae "sudo pkill -3 bf_switchd"

cecho "YELLOW" "Stopping switchd on tofino1c (receiver.p4)"
ssh tofino1c-ae "sudo pkill -3 bf_switchd"

cecho "YELLOW" "Stopping switchd on p4campus-proc1 (topo.p4)"
ssh p4campus-proc1-ae "sudo pkill -3 bf_switchd"

cecho "GREEN" "Done"

cecho "YELLOW" "Clearing bfrt tmux on tofino1a (sender.p4)"
ssh tofino1a-ae "tmux send-keys -t bfrt.0 'cd /home/sigcomm23ae/bf-sde-9.10.0' ENTER C-l"

cecho "YELLOW" "Clearing bfrt tmux on tofino1c (receiver.p4)"
ssh tofino1c-ae "tmux send-keys -t bfrt.0 'cd /home/sigcomm23ae/bf-sde-9.9.0' ENTER C-l"

cecho "YELLOW" "Clearing bfrt tmux on p4campus-proc1 (topo.p4)"
ssh p4campus-proc1-ae "tmux send-keys -t bfrt.0 'cd /home/sigcomm23ae/bf-sde-9.11.1' ENTER C-l"

cecho "GREEN" "Done"

