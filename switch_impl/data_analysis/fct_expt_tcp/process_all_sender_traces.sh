#/bin/bash

mydir=$(dirname $0)

cecho(){  # source: https://stackoverflow.com/a/53463162/2886168
    RED="\033[0;31m"
    GREEN="\033[0;32m"
    YELLOW="\033[0;33m"
    # ... ADD MORE COLORS
    NC="\033[0m" # No Color

    printf "${!1}${2} ${NC}\n"
}

# Check if expt name and number is passed as an argument
if [ $# -lt 5 ];then
    cecho "YELLOW" "Usage: $0 <target_dir> <flow_size in B> <expt_type (motivation/evaluation)> <MTU size: 1068/1500> <no_affected:0 or 1> [--silent]"
    exit 1
fi

silent=0

if [ $# -eq 6 ];then
    if [ "$6" == "--silent" ];then
        silent=1
    else
        echo "Invalid option $6"
        cecho "YELLOW" "Usage: $0 <target_dir> <flow_size in B> <expt_type (motivation/evaluation)> <MTU size: 1068/1500> <no_affected:0 or 1> [--silent]"
        exit 1
    fi
fi

target_dir=$1
flow_size=$2
expt_type=$3
mtu=$4
no_affected=$5

processing_script=$mydir/process_sender_trace.py


sender_file_list=($target_dir/${flow_size}B_sender*.csv)

num_runs=${#sender_file_list[@]}

cecho "YELLOW" "Number of runs found: $num_runs"

for file in "${sender_file_list[@]}";do
    affected_file=${file/"_sender"/"_affected_flows"} # replace _sender in filename
    affected_file=${affected_file/".csv"/".dat"}
    if [ $silent -eq 1 ]; then
        echo "Processing: $file"
        conda run -n lg-data-analysis python3 $processing_script $file $affected_file $flow_size $expt_type $mtu $no_affected > /dev/null
    else
        conda run -n lg-data-analysis python3 $processing_script $file $affected_file $flow_size $expt_type $mtu $no_affected
    fi
done

cecho "YELLOW" "Total runs processed: $num_runs"

# for run in {1..8};do
#     $processing_script $target_dir/${flow_size}KB_sender_run$run.csv $target_dir/${flow_size}KB_affected_flows_run$run.dat
# done


