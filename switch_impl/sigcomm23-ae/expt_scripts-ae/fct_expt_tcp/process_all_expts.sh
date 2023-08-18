#!/bin/bash

mydir=$(dirname $0)

source $mydir/../common/bash_common.sh

process_fct_script=$mydir/../../../data_analysis/fct_expt_tcp/process_fct_expt.sh
calculate_fcts_script=$mydir/../../../data_analysis/fct_expt_tcp/calculate_fcts.py


for expt_name in 10-3 10-3_lg 10-3_lg_nb;do
    # process fct expt
    $process_fct_script ~/traces/fct_expt_tcp/$expt_name 24387 motivation 1500 --no-affected
    # calculate fcts
    echo "#####################################################"
    cecho "YELLOW" "Calculating FCTs"
    echo "#####################################################"
    conda run -n lg-data-analysis python3 $calculate_fcts_script ~/traces/fct_expt_tcp/$expt_name 24387
done
