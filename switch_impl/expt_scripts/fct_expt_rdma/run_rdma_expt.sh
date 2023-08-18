#!/bin/bash

cecho(){  # source: https://stackoverflow.com/a/53463162/2886168
    RED="\033[0;31m"
    GREEN="\033[0;32m"
    YELLOW="\033[0;33m"
    # ... ADD MORE COLORS
    NC="\033[0m" # No Color

    printf "${!1}${2} ${NC}\n"
}

# Check if the script is being run on lumos
hostname=`hostname`
if [[ "$hostname" != "lumos" ]];then
    cecho "RED" "ERROR: This script needs to run on lumos"
    exit 1
fi

# Check if expt name and number is passed as an argument
if [ $# -ne 4 ];then
    cecho "YELLOW" "Usage: $0 <flow size in Bytes> <num of runs (1k flows each)>"
    exit 1
fi

flow_size=$1
num_runs=$2
FLOWS_PER_RUN=1000

# Step 1: Start the RDMA server on hajime
echo "Starting RDMA server on hajime..."
# TODO change this: ssh hajime "sudo ip netns exec lr env TCP_WINDOW_SIZE=8M taskset --cpu-list 2 iperf -s -N ${congestion_control} --logfile ~/traces/linkradar/${set_up}/${path}/${flow_size}/${set_up}.log " > /dev/null & 
ssh hajime "sudo ip netns exec lr ./bin/rdma_server -a 10.2.2.2" # server

# # Step 2: Start tcpdump on patronus
# echo "Starting tcpdump on patronus..."
# ssh patronus "sudo ip netns exec lr tcpdump -i <iface> -s 100 -w ~/traces/linkradar/${path}/${flow_size}/RDMA_WRITE_baseline_run${run}.pcap" > /dev/null &

Step 3: Send flows from lumos
for flow in $(seq 1 $FLOWS_PER_RUN);do
    echo "[Run: $run] Sending flow $flow ..."
    # rdma write client 
    ssh lumos "sudo ip netns exec lr ./bin/rdma_client -a 10.2.2.2 -f /src/${flow_size}B.txt -l /log/out.dat -n ${FLOWS_PER_RUN}"
done

# # Step 4: Stop tcpdump on patronus
# echo "Stopping packet capture on patronus"
# ssh patronus "sudo killall -2 tcpdump"

# Step 5: Stop the RDMA server on hajime
echo "Stopping RDMA server on hajime..."
ssh hajime "sudo killall -2 rdma_server"
ssh lumos "sudo killall -2 rdma_client"



################################################################################################################################################


# if [ $# -eq 2 ] || [ $# -eq 3 ] ; then
# set_up="lr_setup1"
# # else
# #     set_up="lr_setup${set_up}" # avoid killing this process itself
# # fi

# # tofino1b_traces_path="/home/cirlab/jarvis-tofino/linkradar/expt-data/motivation/fct/10_5_FLR/${flow_size}KB"
# # network_losses_script="/home/cirlab/jarvis-tofino/linkradar/motivation/fct/check_network_drops.py"

# # RUN_PD_RPC="/home/cirlab/bf-sde-9.7.0/run_pd_rpc.py"
# # SDE_INSTALL="/home/cirlab/bf-sde-9.7.0/install"



# # LOSS_RATE="10-2"

# cecho "YELLOW" "*** Running FCT expt with flow size ${flow_size}KB for $num_runs runs (10k flows each)"

# #echo "Disable hardware timestam on lumos ..."
# #sudo ip netns exec lr hwstamp_ctl -i ens2f1 -r 0 -t 0
# #echo "Disable hardware timestam on hajime ..."
# #ssh hajime "sudo ip netns exec lr hwstamp_ctl -i enp6s0f1np1 -r 0 -t 0"

# echo "Flush TCP metrics on lumos ..."
# sudo ip netns exec lr ip tcp_metrics flush
# echo "Flush TCP metrics on hajime ..."
# ssh hajime "sudo ip netns exec lr ip tcp_metrics flush"


# echo "Switch to high performance mode on lumos ..."
# sudo ip netns exec lr sh -c "echo 'GOVERNOR=\"performance\"' > /etc/default/cpufrequtils"
# sudo ip netns exec lr systemctl restart cpufrequtils.service
# echo "Switch to high performance mode on hajime ..."
# ssh hajime "sudo ip netns exec lr sh -c \"echo 'GOVERNOR=\"performance\"' > /etc/default/cpufrequtils\""
# ssh hajime "sudo ip netns exec lr systemctl restart cpufrequtils.service"

# echo "Disabling TCP timestamps on lumos ..."
# sudo ip netns exec lr sysctl net.ipv4.tcp_timestamps=0
# echo "Disabling TCP timestamps on hajime ..."
# ssh hajime "sudo ip netns exec lr sysctl net.ipv4.tcp_timestamps=0"

# echo "Enabling TCP SACK on lumos ..."
# sudo ip netns exec lr sysctl net.ipv4.tcp_sack=1
# echo "Enabling TCP SACK on hajime ..."
# ssh hajime "sudo ip netns exec lr sysctl net.ipv4.tcp_sack=1"

# echo "Enabling TCP ECN on lumos ..."
# sudo ip netns exec lr sysctl net.ipv4.tcp_ecn=1
# echo "Enabling TCP ECN on hajime ..."
# ssh hajime "sudo ip netns exec lr sysctl net.ipv4.tcp_ecn=1"

# echo "Disabling tcp_no_save on lumos ..."
# sudo ip netns exec lr sysctl net.ipv4.tcp_no_metrics_save=0
# echo "Disabling tcp_no_save  on hajime ..."
# ssh hajime "sudo ip netns exec lr sysctl net.ipv4.tcp_no_metrics_save=0"

# echo "Enabling tcp_recovery on lumos ..."
# sudo ip netns exec lr sysctl net.ipv4.tcp_recovery=1
# echo "Enabling tcp_recovery  on hajime ..."
# ssh hajime "sudo ip netns exec lr sysctl net.ipv4.tcp_recovery=10"

# echo "Enabling tcp_early_retrans on lumos ..."
# sudo ip netns exec lr sysctl net.ipv4.tcp_early_retrans=3
# echo "Enabling tcp_early_retrans  on hajime ..."
# ssh hajime "sudo ip netns exec lr sysctl net.ipv4.tcp_early_retrans=3"

# echo "Setting rto_min on lumos ..."
# sudo ip netns exec lr ip route change 10.2.2.0/24 via 10.2.2.1 dev ens2f1 rto_min 1ms
# echo "Setting rto_min on hajime ..."
# ssh hajime "sudo ip netns exec lr ip route change 10.2.2.0/24 via 10.2.2.2 dev enp6s0f1np1 rto_min 1ms"

# # TODO set initcwnd and initrwnd to 10 on both sender and receiver

# #cecho "YELLOW" "*** Setting flow size inside the network losses script"
# #ssh tofino1b "sed -i \"s/flow_size =.*/flow_size = $flow_size/\" ${network_losses_script}"
# #cecho "YELLOW" "*** Creating directory for network losses dumps"
# #ssh tofino1b "mkdir -p $tofino1b_traces_path"

# echo "Creating directory storing traces"
# mkdir -p ~/traces/linkradar/${set_up}/${path}/${flow_size}
# ssh hajime "mkdir -p ~/traces/linkradar/${set_up}/${path}/${flow_size}"
# if [ "$expt_type" = "motivation" ] ; then
#     ssh tina "mkdir -p  ~/traces/linkradar/${set_up}/${path}/${flow_size}"
# elif [ "$expt_type" = "evaluation" ]; then 
#     mkdir -p ~/traces/linkradar/${set_up}/${path}/${flow_size} # on lumos itself
# else
#     echo "Invalid expt_type: ${expt_type}"
#     exit 1
# fi

# for run in $(seq 1 $num_runs);do
#     cecho "YELLOW" "**********************************************"
#     cecho "YELLOW" "********       Run $run     ******************"
#     cecho "YELLOW" "**********************************************"

#     cecho "YELLOW" "*** [Run: $run] Setting up tcpdump captures and iperf server..."
#     echo "Starting iperf server on hajime..."
#     ssh hajime "sudo ip netns exec lr env TCP_WINDOW_SIZE=8M taskset --cpu-list 2 iperf -s -N ${congestion_control} --logfile ~/traces/linkradar/${set_up}/${path}/${flow_size}/${set_up}.log " > /dev/null &

#     if [ "$expt_type" = "motivation" ] ; then
#         echo "Starting tcpdump on tina..."
#         ssh tina "sudo ip netns exec lr tcpdump -i ens2f0 -s 100 --time-stamp-precision=nano -w ~/traces/linkradar/${set_up}/${path}/${flow_size}/${flow_size}KB_affected_flows_run${run}.pcap tcp" > /dev/null &
#     elif [ "$expt_type" = "evaluation" ]; then 
#         echo "Starting tcpdump on lumos (affected flows)..."
#         sudo ip netns exec lr_affected tcpdump -i ens3f0 -s 100 --time-stamp-precision=nano -w ~/traces/linkradar/${set_up}/${path}/${flow_size}/${flow_size}KB_affected_flows_run${run}.pcap tcp > /dev/null &
#     fi

#     sleep 1

#     echo "Starting tcpdump on lumos..."
#     sudo ip netns exec lr tcpdump -i ens2f1 -s 100 --time-stamp-precision=nano -w ~/traces/linkradar/${set_up}/${path}/${flow_size}/${flow_size}KB_sender_run${run}.pcap tcp > /dev/null &


#     echo "Starting tcpdump on hajime..."
#     ssh hajime "sudo ip netns exec lr tcpdump -i enp6s0f1np1 -s 100 --time-stamp-precision=nano -w ~/traces/linkradar/${set_up}/${path}/${flow_size}/${flow_size}KB_receiver_run${run}.pcap tcp" > /dev/null &
#     sleep 5

#     cecho "YELLOW" "*** [Run: $run] Starting flows from lumos..."

#     for flow in $(seq 1 $FLOWS_PER_RUN);do
#         echo "[Run: $run] Sending flow $flow ..."
#         sudo ip netns exec lr env TCP_WINDOW_SIZE=8M taskset --cpu-list 2 iperf -c 10.2.2.2 -n ${flow_size}k -N ${congestion_control} > /dev/null
#     done

#     sleep 4

#     cecho "YELLOW" "*** [Run: $run] Cleaning up"
#     echo "Stopping iperf server on hajime..."
#     #ssh hajime "sudo killall -2 iperf"
#     ssh hajime "sudo pkill -f \"${set_up}\""

#     echo "Stopping packet capture on tina"
#     #ssh tina "sudo killall -2 tcpdump"
#     ssh tina "sudo pkill -f \"${set_up}\""

#     echo "Stopping packet capture on lumos"
#     #sudo killall -2 tcpdump
#     sudo pkill -f "${set_up}"

#     echo "Stopping packet capture on hajime"
#     #ssh hajime "sudo killall -2 tcpdump"
#     ssh hajime "sudo pkill -f \"${set_up}\""

#     # cecho "YELLOW" "*** [Run: $run] Checking for any network losses..."
#     # network_loss_outfile=$tofino1b_traces_path"/${flow_size}KB_netlosses_run${run}_off.dat"
#     # # Rename inside the run_pd_rpc script
#     # echo "Outfile: $network_loss_outfile"
#     # ssh tofino1b "sed -i \"s/run =.*/run = $run/\" ${network_losses_script}"
    
#     # # Collected 
#     # ssh tofino1b "env SDE_INSTALL=${SDE_INSTALL} ${RUN_PD_RPC} ${network_losses_script} > /dev/null 2>&1"
    
#     sleep 2
    
# done





# echo "Switch to moderate performance mode on lumos ..."
# sudo ip netns exec lr sh -c "echo 'GOVERNOR=\"ondemand\"' > /etc/default/cpufrequtils"
# sudo ip netns exec lr systemctl restart cpufrequtils.service
# echo "Switch to moderate performance mode on hajime ..."
# ssh hajime "sudo ip netns exec lr sh -c \"echo 'GOVERNOR=\"ondemand\"' > /etc/default/cpufrequtils\""
# ssh hajime "sudo ip netns exec lr systemctl restart cpufrequtils.service"


# if [ "$(whoami)" = "raj" ]; then
#     echo "Running Raj's IFTTT webhook"
#     curl -X POST -H "Content-Type: application/json" -d "{\"value1\":\"${flow_size}KB_FCT\"}" https://maker.ifttt.com/trigger/Script_Expt_completed/with/key/gB88SULNID5Te0obIzRqK-6a-6EO6tHSSBT5ulPEBbT
# elif [ "$(whoami)" = "qi" ]; then
#     echo "Running Qi's IFTTT webhook"
#     curl -X POST -H "Content-Type: application/json" -d "{\"value1\":\"${flow_size}KB_FCT\"}" https://maker.ifttt.com/trigger/notify/with/key/KaSJAeA55RPHo2JvsvAMO
# fi


