#!/bin/bash

cecho(){  # source: https://stackoverflow.com/a/53463162/2886168
    RED="\033[0;31m"
    GREEN="\033[0;32m"
    YELLOW="\033[0;33m"
    # ... ADD MORE COLORS
    NC="\033[0m" # No Color

    printf "${!1}${2} ${NC}\n"
}

mydir=$(dirname $0)

fct_expt_dir=~/linkguardian/switch_impl/expt_scripts/fct_expt_rdma

# Check if the script is being run on lumos
hostname=`hostname`
if [[ "$hostname" != "lumos" ]];then
    cecho "RED" "ERROR: This script needs to run on lumos"
    exit 1
fi

# Check if expt name and number is passed as an argument
if [ $# -ne 3 ];then
    cecho "YELLOW" "Usage: $0 <flow size in Bytes> <num of flow trials> <expt_name>"
    exit 1
fi

flow_size=$1
num_flow_trials=$2
expt_name=$3

cecho "YELLOW" "######  Running RDMA FCT expt '$expt_name' for $num_flow_trials flow trials  ######"

# Step 1: Start the RDMA server on caelus-ae-ae
cecho "YELLOW" "Starting RDMA server on caelus..."
ssh caelus-ae "sudo ip netns exec lg $fct_expt_dir/bin/rdma_server -a 10.2.2.2" > /dev/null & # server

sleep 3

# # Step 1.1: Start tcpdump on patronus
# echo "Starting tcpdump on patronus..."
# ssh patronus "sudo ip netns exec lg tcpdump -i <iface> -s 100 -w ~/traces/linkradar/${path}/${flow_size}/RDMA_WRITE_baseline_run${run}.pcap" > /dev/null &

# Step 2: Send flows from lumos
cecho "YELLOW" "Starting RDMA client on lumos..."
    # rdma write client 
    sudo ip netns exec lg $mydir/bin/rdma_client -a 10.2.2.2 -f /src/${flow_size}B.txt -l ~/traces/fct_expt_rdma/$expt_name.dat -n $num_flow_trials
# done

# Step 3: Stop the RDMA server on caelus and client on lumos
echo ""
cecho "YELLOW" "Stopping RDMA server on caelus..."
ssh caelus-ae "sudo killall -2 rdma_server"
# sudo killall -2 rdma_client
cecho "GREEN" "Done"


# if [ "$(whoami)" = "raj" ]; then
#     echo "Running Raj's IFTTT webhook"
#     curl -X POST -H "Content-Type: application/json" -d "{\"value1\":\"${flow_size}KB_FCT\"}" https://maker.ifttt.com/trigger/Script_Expt_completed/with/key/gB88SULNID5Te0obIzRqK-6a-6EO6tHSSBT5ulPEBbT
# elif [ "$(whoami)" = "qi" ]; then
#     echo "Running Qi's IFTTT webhook"
#     curl -X POST -H "Content-Type: application/json" -d "{\"value1\":\"${flow_size}KB_FCT\"}" https://maker.ifttt.com/trigger/notify/with/key/KaSJAeA55RPHo2JvsvAMO
# fi


