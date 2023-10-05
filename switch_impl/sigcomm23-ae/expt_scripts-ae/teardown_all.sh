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
