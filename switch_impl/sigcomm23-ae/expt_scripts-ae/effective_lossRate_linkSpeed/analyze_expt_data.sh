#!/bin/bash

my_dir="$(dirname "$0")"
source $my_dir/../common/bash_common.sh

if [ $# -ne 3 ]; then
    cecho "YELLOW" "Usage: $0 <expt_name> <1/0 blocking or non-blocking> <path to directory>"
    exit 1
fi

PYTHON_INTERPRETER=/home/sigcomm23ae/miniconda3/envs/lg-data-analysis/bin/python3

expt_name=$1
mode=$2
dirpath=$3

$PYTHON_INTERPRETER $my_dir/../../../data_analysis/effective_lossRate_linkSpeed/analyze_expt_data.py $expt_name $mode $dirpath
