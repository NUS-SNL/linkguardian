#!/bin/bash

mydir=$(dirname $0)

source $mydir/../common/bash_common.sh

if [ $# -ne 2 ];then
    cecho "YELLOW" "Usage: $0 <expt_name> <num of runs (1k flows each)>"
    exit 1
fi


mydir=$(dirname $0)
expt_name=$1
num_runs=$2

EXPT_SCRIPT=$mydir/../../../expt_scripts/fct_expt_tcp/run_expt.sh

$EXPT_SCRIPT 24387 $num_runs dctcp 1500 $expt_name none
