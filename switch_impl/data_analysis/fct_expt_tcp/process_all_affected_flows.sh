#/bin/bash


cecho(){  # source: https://stackoverflow.com/a/53463162/2886168
    RED="\033[0;31m"
    GREEN="\033[0;32m"
    YELLOW="\033[0;33m"
    # ... ADD MORE COLORS
    NC="\033[0m" # No Color

    printf "${!1}${2} ${NC}\n"
}

# Check if expt name and number is passed as an argument
if [ $# -ne 2 ];then
    cecho "YELLOW" "Usage: $0 <target_dir> <flow_size in B>"
    exit 1
fi

target_dir=$1
flow_size=$2


processing_script=/home/raj/workspace/linkradar/data-analysis/motivation/fct/process_affected_flows.py

file_list=($target_dir/${flow_size}B_affected_flows*.csv)

num_runs=${#file_list[@]}

cecho "YELLOW" "Number of runs found: $num_runs"

for file in "${file_list[@]}";do
    $processing_script $file
done

cecho "YELLOW" "Total runs processed: $num_runs"

