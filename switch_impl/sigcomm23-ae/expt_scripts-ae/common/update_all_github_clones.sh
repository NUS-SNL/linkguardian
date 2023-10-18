#!/bin/bash

mydir=`dirname $0`

source $mydir/bash_common.sh

cecho "YELLOW" "Updating GitHub clone on lumos..."
cd ~/linkguardian && git pull

cecho "YELLOW" "Updating GitHub clone on caelus..."
ssh caelus-ae "cd ~/linkguardian && git pull"

cecho "YELLOW" "Updating GitHub clone on tofino1a..."
ssh tofino1a-ae "cd ~/linkguardian && git pull"

cecho "YELLOW" "Updating GitHub clone on tofino1c..."
ssh tofino1c-ae "cd ~/linkguardian && git pull"

cecho "YELLOW" "Updating GitHub clone on p4campus-proc1"
ssh p4campus-proc1-ae "cd ~/linkguardian && git pull"

