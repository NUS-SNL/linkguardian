#!/bin/bash

mydir=$(dirname $0)

source $mydir/../common/bash_common.sh

process_fct_script=$mydir/../../../data_analysis/fct_expt_rdma_fast/process_fct_expt.sh
descriptive_stats_script=$mydir/../../../data_analysis/common/get_descriptive_stats.py

declare -A expt_display_name
expt_display_name["10-3"]="No_Protection"
expt_display_name["10-3_lg"]="LinkGuardian"
expt_display_name["10-3_lg_nb"]="LinkGuardianNB"

# calculate_fcts_script=$mydir/../../../data_analysis/fct_expt_rdma_fast/calculate_fcts.py



for expt_name in 10-3 10-3_lg 10-3_lg_nb;do
    echo -n "Processing expt $expt_name (${expt_display_name["$expt_name"]})... "
    cecho "GREEN" "Done"
    # process fct expt
    $process_fct_script ~/traces/fct_expt_rdma/$expt_name.log
    # calculate fct distribution
    conda run -n lg-data-analysis python3 $descriptive_stats_script ~/traces/fct_expt_rdma/$expt_name.dat ${expt_display_name["$expt_name"]} > /dev/null
done
