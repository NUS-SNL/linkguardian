#!/bin/bash

my_dir="$(dirname "$0")"

source $my_dir/common/bash_common.sh

# compile receiver.p4 on tofino1c
cecho "YELLOW" "Compiling receiver.p4 on tofino1c"
ssh tofino1c-ae "cd ~/bf-sde-9.9.0 && source ./set_sde.bash && ./p4_build.sh ../linkguardian/switch_impl/system_impl/receiver/receiver.p4"

echo ""

# compile sender.p4 on tofino1a
cecho "YELLOW" "Compiling sender.p4 on tofino1a"
ssh tofino1a-ae "cd ~/bf-sde-9.10.0 && source ./set_sde.bash && ./p4_build.sh ../linkguardian/switch_impl/system_impl/sender/sender.p4"

echo ""

# compile topo.p4 on p4campus-proc1
cecho "YELLOW" "Compiling topo.p4 on p4campus-proc1"
ssh p4campus-proc1-ae "cd ~/bf-sde-9.11.1 && source ./set_sde.bash && ./p4_build.sh ../linkguardian/switch_impl/topo_impl/topo.p4"

