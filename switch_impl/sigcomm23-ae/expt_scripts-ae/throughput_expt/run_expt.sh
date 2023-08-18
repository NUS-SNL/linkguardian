#!/bin/bash

mydir=$(dirname $0)

source $mydir/../common/bash_common.sh

if [ $# -ne 1 ];then
    cecho "YELLOW" "Usage: $0 <expt_name>"
    exit 1
fi

expt_name=$1

EXPT_SCRIPT=$mydir/../../../expt_scripts/throughput_expt/run_throughput_expt.sh

$EXPT_SCRIPT 5 $expt_name cubic 70


