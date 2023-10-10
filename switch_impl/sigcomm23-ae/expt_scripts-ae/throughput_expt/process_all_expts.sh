#!/bin/bash

mydir=$(dirname $0)

source $mydir/../common/bash_common.sh

json_parsing_script=$mydir/../../../data_analysis/throughput_expt/parse_iperf3_json.py
throughput_processing_script=$mydir/../../../data_analysis/throughput_expt/get_avg_throughput.py

declare -A expt_display_name
expt_display_name["10-3"]="No_Protection"
expt_display_name["10-3_lg"]="LinkGuardian"
expt_display_name["10-3_lg_nb"]="LinkGuardianNB"

printf "%15s\t\t%s\n" "expt_name" "avg_throughput(Gbps)"

for expt_name in 10-3 10-3_lg 10-3_lg_nb; do
    # first parse the json file
    conda run -n lg-data-analysis python3 $json_parsing_script ~/traces/throughput_expt/$expt_name-cubic.json
    # then process the data file
    avg_throughput=`conda run -n lg-data-analysis python3 ../../data_analysis/throughput_expt/get_avg_throughput.py ~/traces/throughput_expt/$expt_name-cubic.dat 5 | grep Avg | cut -d':' -f2`
    
    printf "%15s\t\t%s\n" ${expt_display_name["$expt_name"]} $avg_throughput 

    # printf "%10s\t%s\n" $expt_name $avg_throughput 
done







