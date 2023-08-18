#!/bin/bash

cecho(){  # source: https://stackoverflow.com/a/53463162/2886168
    RED="\033[0;31m"
    GREEN="\033[0;32m"
    YELLOW="\033[0;33m"
    # ... ADD MORE COLORS
    NC="\033[0m" # No Color

    printf "${!1}${2} ${NC}\n"
}

setup=5 # sigcomm23ae setup
FLOWS_PER_RUN=1000

traces_path=""

if [ $setup == 1 ];then
tx_server=lumos
rx_server=hajime
namespace=lr
tx_iface=ens2f1
tx_ip=10.2.2.1
rx_iface=enp6s0f1
rx_ip=10.2.2.2
network=10.2.2.0
elif [ $setup == 2 ];then
tx_server=lumos
rx_server=caelus
namespace=lr
tx_iface=ens2f1
tx_ip=10.2.2.1
rx_iface=ens1f1
rx_ip=10.2.2.2
network=10.2.2.0
elif [ $setup == 3 ];then
tx_server=lumos
rx_server=caelus
namespace=lr_cx6
tx_iface=ens3f1
tx_ip=10.2.2.1
rx_iface=enp177s0f1
rx_ip=10.2.2.2
network=10.2.2.0
elif [ $setup == 4 ];then
tx_server=patronus
rx_server=knowhere
namespace=lr_devtest
tx_iface=ens3f1
tx_ip=10.1.1.1
rx_iface=ens4f1
rx_ip=10.1.1.2
network=10.1.1.0
elif [ $setup == 5 ];then
tx_server=lumos
rx_server=caelus-ae
namespace=lg
tx_iface=ens3f1
tx_ip=10.2.2.1
rx_iface=enp177s0f1
rx_ip=10.2.2.2
network=10.2.2.0
traces_path=~/traces/fct_expt_tcp
cpu_power_script=/home/sigcomm23ae/linkguardian/switch_impl/expt_scripts/cpu_power_scripts/performance_mode_pstate.sh
else 
    echo "RED" "ERROR: invalid setup $setup"
    exit 1
fi

# Check if the script is being run on $tx_server
hostname=`hostname`
if [[ "$hostname" != "$tx_server" ]];then
    cecho "RED" "ERROR: This script needs to run on $tx_server"
    exit 1
fi

# Check if expt name and number is passed as an argument
if [ $# -ne 6 ];then
    cecho "YELLOW" "Usage: $0 <flow size in Bytes (iperf notation)> <num of runs (1k flows each)> <congestion control algorithm to use (cubic/bbr/dctcp)> <MTU size: 1068/1500> <expt_name e.g. baseline> <expt type: (motivation/evaluation/none)>"
    cecho "YELLOW" "expt type:"
    echo "evaluation: rand drop affected flows on $tx_server ens3f0 (lr_affected)"
    echo "none/motivation: no capturing of affected flows"
    exit 1
fi

# MTU sizes: 1068 (motivation), 1500 (otherwise)
# sudo ip link set dev $tx_iface mtu 1068

flow_size=$1
num_runs=$2
congestion_control=$3
mtu_size=$4
expt_name=$5
expt_type=$6

if [ -z "$traces_path" ];then # not overrridden
# traces_path=~/traces/linkradar/evaluation/modes_comparison
# traces_path=~/traces/linkradar/evaluation/tail_loss_fct
traces_path=~/traces/linkradar/motivation_fct
# traces_path=~/traces/linkradar/evaluation/normal_fct
fi


# Check the congestion control algorithm
if [ $congestion_control = "cubic" ] ; then
    congestion_control_option="-Z cubic"
elif [ $congestion_control = "bbr" ] ; then
    congestion_control_option="-Z bbr"
elif [ $congestion_control = "dctcp" ] ; then
    congestion_control_option="-Z dctcp"
else
    cecho "YELLOW" "ERROR: The specified congestion control algorithm is not supported by the script."
    exit 1
fi


# Check MTU size
if [ $mtu_size -ne 1500 ] && [ $mtu_size -ne 1068 ]; then
    cecho "YELLOW" "ERROR: The specified MTU size $mtu_size is incorrect. Specify either 1500 or 1068"
    exit 1
fi


# if [ $# -eq 2 ] || [ $# -eq 3 ] ; then
# set_up="lr_setup1"
# else
#     set_up="lr_setup${set_up}" # avoid killing this process itself
# fi

# tofino1b_traces_path="/home/cirlab/jarvis-tofino/linkradar/expt-data/motivation/fct/10_5_FLR/${flow_size}KB"
# network_losses_script="/home/cirlab/jarvis-tofino/linkradar/motivation/fct/check_network_drops.py"

# RUN_PD_RPC="/home/cirlab/bf-sde-9.7.0/run_pd_rpc.py"
# SDE_INSTALL="/home/cirlab/bf-sde-9.7.0/install"



# LOSS_RATE="10-2"

cecho "YELLOW" "*** Running FCT expt with flow size ${flow_size} (MTU: $mtu_size) for $num_runs runs ($FLOWS_PER_RUN flows each)"

# scheduled_sleep_secs=9000

# cecho "YELLOW" "Sleeping for scheduled $scheduled_sleep_secs secs..."
# for ((i=1; i<=$scheduled_sleep_secs; i++))
# do
#     sleep 1
#     echo "$i/$scheduled_sleep_secs"
# done


echo "Flush TCP metrics on $tx_server ..."
sudo ip netns exec $namespace ip tcp_metrics flush
echo "Flush TCP metrics on $rx_server ..."
ssh $rx_server "sudo ip netns exec $namespace ip tcp_metrics flush"

if [ $setup == 1 ];then
    echo "Switch to high performance mode on $tx_server ..."
    sudo ip netns exec $namespace sh -c "echo 'GOVERNOR=\"performance\"' > /etc/default/cpufrequtils"
    sudo ip netns exec $namespace systemctl restart cpufrequtils.service
    echo "Switch to high performance mode on $rx_server ..."
    ssh $rx_server "sudo ip netns exec $namespace sh -c \"echo 'GOVERNOR=\"performance\"' > /etc/default/cpufrequtils\""
    ssh $rx_server "sudo ip netns exec $namespace systemctl restart cpufrequtils.service"
elif [ $setup == 2 ] || [ $setup == 3 ];then
    echo "Switch to high performance mode on $tx_server ..."
    # acpi-cpufreq not working anymore on Lumos
    # sudo ip netns exec $namespace sh -c "echo 'GOVERNOR=\"performance\"' > /etc/default/cpufrequtils"
    # sudo ip netns exec $namespace systemctl restart cpufrequtils.service
    sudo /home/raj/performance_mode_pstate.sh enable > /dev/null

    echo "Switch to high performance mode on $rx_server ..."
    ssh $rx_server "/home/raj/performance_mode_pstate.sh enable" > /dev/null
elif [ $setup == 5 ];then
    echo "Switch to high performance mode on $tx_server ..."
    sudo $cpu_power_script enable > /dev/null
    echo "Switch to high performance mode on $rx_server ..."
    ssh $rx_server "$cpu_power_script enable" > /dev/null
fi

echo "Setting mtu to $mtu_size on $tx_server ..."
sudo ip netns exec $namespace ip link set $tx_iface mtu $mtu_size
echo "Setting mtu to $mtu_size on $rx_server ..."
ssh $rx_server "sudo ip netns exec $namespace ip link set $rx_iface mtu $mtu_size"

echo "Setting NIC ring buffers to maximum on $tx_server ..."
sudo ip netns exec $namespace ethtool -G $tx_iface tx 8192 rx 8192
echo "Setting NIC ring buffers to maximum on $rx_server ..."
ssh $rx_server "sudo ip netns exec $namespace ethtool -G $rx_iface tx 8192 rx 8192"

echo "Disabling hardware timestamp on $tx_server ..."
sudo ip netns exec $namespace hwstamp_ctl -i $tx_iface -r 0 -t 0
echo "Disabling hardware timestamp on $rx_server ..."
ssh $rx_server "sudo ip netns exec $namespace hwstamp_ctl -i $rx_iface -r 0 -t 0"

echo "Disabling TCP timestamps on $tx_server ..."
sudo ip netns exec $namespace sysctl net.ipv4.tcp_timestamps=0
echo "Disabling TCP timestamps on $rx_server ..."
ssh $rx_server "sudo ip netns exec $namespace sysctl net.ipv4.tcp_timestamps=0"

echo "Enabling TCP SACK on $tx_server ..."
sudo ip netns exec $namespace sysctl net.ipv4.tcp_sack=1
echo "Enabling TCP SACK on $rx_server ..."
ssh $rx_server "sudo ip netns exec $namespace sysctl net.ipv4.tcp_sack=1"

if [ $congestion_control = "cubic" ] ; then
    echo "Disabling TCP ECN on $tx_server ..."
    sudo ip netns exec $namespace sysctl net.ipv4.tcp_ecn=0
    echo "Disabling TCP ECN on $rx_server ..."
    ssh $rx_server "sudo ip netns exec $namespace sysctl net.ipv4.tcp_ecn=0"
elif [ $congestion_control = "dctcp" ] ; then
    echo "Enabling TCP ECN on $tx_server ..."
    sudo ip netns exec $namespace sysctl net.ipv4.tcp_ecn=1
    echo "Enabling TCP ECN on $rx_server ..."
    ssh $rx_server "sudo ip netns exec $namespace sysctl net.ipv4.tcp_ecn=1"
fi

echo "Enabling tcp_no_save on $tx_server ..."
sudo ip netns exec $namespace sysctl net.ipv4.tcp_no_metrics_save=1
echo "Enabling tcp_no_save on $rx_server ..."
ssh $rx_server "sudo ip netns exec $namespace sysctl net.ipv4.tcp_no_metrics_save=1"

echo "Enabling tcp_recovery on $tx_server ..."
sudo ip netns exec $namespace sysctl net.ipv4.tcp_recovery=1
echo "Enabling tcp_recovery  on $rx_server ..."
ssh $rx_server "sudo ip netns exec $namespace sysctl net.ipv4.tcp_recovery=1"

echo "Enabling tcp_early_retrans on $tx_server ..."
sudo ip netns exec $namespace sysctl net.ipv4.tcp_early_retrans=3
echo "Enabling tcp_early_retrans  on $rx_server ..."
ssh $rx_server "sudo ip netns exec $namespace sysctl net.ipv4.tcp_early_retrans=3"

echo "Setting rto_min on $tx_server ..."
sudo ip netns exec $namespace ip route change $network/24 via $tx_ip dev $tx_iface rto_min 1ms
echo "Setting rto_min on $rx_server ..."
ssh $rx_server "sudo ip netns exec $namespace ip route change $network/24 via $rx_ip dev $rx_iface rto_min 1ms"

# TODO set initcwnd and initrwnd to 10 on both sender and receiver

#cecho "YELLOW" "*** Setting flow size inside the network losses script"
#ssh tofino1b "sed -i \"s/flow_size =.*/flow_size = $flow_size/\" ${network_losses_script}"
#cecho "YELLOW" "*** Creating directory for network losses dumps"
#ssh tofino1b "mkdir -p $tofino1b_traces_path"

echo "Creating directories for storing traces"
if [ $setup == 5 ];then
    mkdir -p $traces_path/$expt_name
    ssh $rx_server "mkdir -p $traces_path/$expt_name"
else  # default path structure
    mkdir -p $traces_path/$congestion_control/${flow_size}/$expt_name
    ssh $rx_server "mkdir -p $traces_path/$congestion_control/${flow_size}/$expt_name"
fi

if [ $setup == 4 ]; then 
    # We are not running on lumos. But lumos is used for affected flows
    ssh lumos "mkdir -p $traces_path/$congestion_control/${flow_size}/$expt_name"
fi

# if [ "$expt_type" = "motivation" ] ; then
#     ssh tina "mkdir -p  ~/traces/linkradar/${path}/${flow_size}"
# elif [ "$expt_type" = "evaluation" ]; then 
#     mkdir -p ~/traces/linkradar/${path}/${flow_size} # on $tx_server itself
# else
#     echo "Invalid expt_type: ${expt_type}"
#     exit 1
# fi

echo "Sleeping 10 secs for performance mode to come into effect..."
sleep 10

for run in $(seq 1 $num_runs);do
    cecho "YELLOW" "**********************************************"
    cecho "YELLOW" "********       Run $run     ******************"
    cecho "YELLOW" "**********************************************"

    cecho "YELLOW" "*** [Run: $run] Setting up tcpdump captures and iperf server..."
    echo "Starting iperf server on $rx_server..."
    ssh $rx_server "sudo ip netns exec $namespace env TCP_WINDOW_SIZE=8M taskset --cpu-list 2 iperf -s -N ${congestion_control_option} " > /dev/null &

    # if [ "$expt_type" = "motivation" ] ; then
    #     echo "Starting tcpdump on tina..."
    #     ssh tina "sudo ip netns exec $namespace tcpdump -i ens2f0 -s 100 --time-stamp-precision=nano -w ~/traces/linkradar/${set_up}/${path}/${flow_size}/${flow_size}KB_affected_flows_run${run}.pcap tcp" > /dev/null &
    # el
    if [ "$expt_type" = "evaluation" ]; then 
        echo "Starting tcpdump on lumos (affected flows)..."
        if [ $setup == 1 ];then
            sudo ip netns exec lr_affected tcpdump -i ens3f0 -s 100 --time-stamp-precision=nano -w $traces_path/$congestion_control/${flow_size}/$expt_name/${flow_size}B_affected_flows_run${run}.pcap tcp > /dev/null &
        elif [ $setup == 2 ];then
            ssh lumos "sudo ip netns exec lr_affected tcpdump -i ens3f0 -s 100 --time-stamp-precision=nano -w $traces_path/$congestion_control/${flow_size}/$expt_name/${flow_size}B_affected_flows_run${run}.pcap tcp" > /dev/null &
        fi
    fi

    sleep 1

    echo "Starting tcpdump on $tx_server..."
    if [ $setup == 5 ]; then
        sudo ip netns exec $namespace tcpdump -i $tx_iface -s 100 --time-stamp-precision=nano -w $traces_path/$expt_name/${flow_size}B_sender_run${run}.pcap tcp > /dev/null &
    else 
        sudo ip netns exec $namespace tcpdump -i $tx_iface -s 100 --time-stamp-precision=nano -w $traces_path/$congestion_control/${flow_size}/$expt_name/${flow_size}B_sender_run${run}.pcap tcp > /dev/null &
    fi


    echo "Starting tcpdump on $rx_server..."
    if [ $setup == 5 ]; then
        ssh $rx_server "sudo ip netns exec $namespace tcpdump -i $rx_iface -s 100 --time-stamp-precision=nano -w $traces_path/$expt_name/${flow_size}B_receiver_run${run}.pcap tcp" > /dev/null &
    else
        ssh $rx_server "sudo ip netns exec $namespace tcpdump -i $rx_iface -s 100 --time-stamp-precision=nano -w $traces_path/$congestion_control/${flow_size}/$expt_name/${flow_size}B_receiver_run${run}.pcap tcp" > /dev/null &
    fi
    sleep 5

    cecho "YELLOW" "*** [Run: $run] Starting flows from $tx_server..."

    for flow in $(seq 1 $FLOWS_PER_RUN);do
        echo "[Run: $run] Sending flow $flow ..."
        sudo ip netns exec $namespace env TCP_WINDOW_SIZE=8M taskset --cpu-list 2 iperf -c $rx_ip -n ${flow_size} -N ${congestion_control_option} > /dev/null
    done

    sleep 4

    cecho "YELLOW" "*** [Run: $run] Cleaning up"
    echo "Stopping iperf server on $rx_server..."
    ssh $rx_server "sudo killall -2 iperf"
    # ssh $rx_server "sudo pkill -f \"${set_up}\""

    if [ $setup == 2 ];then
    echo "Stopping packet capture on lumos (affected flows)"
    ssh lumos "sudo killall -2 tcpdump"
    fi
    # ssh tina "sudo pkill -f \"${set_up}\""

    echo "Stopping packet capture on $tx_server"
    sudo killall -2 tcpdump
    # sudo pkill -f "${set_up}"

    echo "Stopping packet capture on $rx_server"
    ssh $rx_server "sudo killall -2 tcpdump"
    # ssh $rx_server "sudo pkill -f \"${set_up}\""

    # cecho "YELLOW" "*** [Run: $run] Checking for any network losses..."
    # network_loss_outfile=$tofino1b_traces_path"/${flow_size}KB_netlosses_run${run}_off.dat"
    # # Rename inside the run_pd_rpc script
    # echo "Outfile: $network_loss_outfile"
    # ssh tofino1b "sed -i \"s/run =.*/run = $run/\" ${network_losses_script}"
    
    # # Collected 
    # ssh tofino1b "env SDE_INSTALL=${SDE_INSTALL} ${RUN_PD_RPC} ${network_losses_script} > /dev/null 2>&1"
    
    sleep 2
    
done

if [ $setup == 1 ];then 
echo "Switch to moderate performance mode on $tx_server ..."
sudo ip netns exec $namespace sh -c "echo 'GOVERNOR=\"ondemand\"' > /etc/default/cpufrequtils"
sudo ip netns exec $namespace systemctl restart cpufrequtils.service
echo "Switch to moderate performance mode on $rx_server ..."
ssh $rx_server "sudo ip netns exec $namespace sh -c \"echo 'GOVERNOR=\"ondemand\"' > /etc/default/cpufrequtils\""
ssh $rx_server "sudo ip netns exec $namespace systemctl restart cpufrequtils.service"
elif [ $setup == 2 ] || [ $setup == 3 ];then 
echo "Switch to moderate performance mode on $tx_server ..."
# acpi-cpufreq not working anymore on Lumos
# sudo ip netns exec $namespace sh -c "echo 'GOVERNOR=\"ondemand\"' > /etc/default/cpufrequtils"
# sudo ip netns exec $namespace systemctl restart cpufrequtils.service
sudo /home/raj/performance_mode_pstate.sh disable > /dev/null
echo "Switch to moderate performance mode on $rx_server ..."
ssh $rx_server "/home/raj/performance_mode_pstate.sh disable" > /dev/null
elif [ $setup == 5 ];then 
echo "Switch to moderate performance mode on $tx_server ..."
sudo $cpu_power_script disable > /dev/null
echo "Switch to moderate performance mode on $rx_server ..."
ssh $rx_server "$cpu_power_script disable" > /dev/null
fi


if [ $congestion_control = "dctcp" ] ; then
    echo "Disabling TCP ECN on $tx_server ..."
    sudo ip netns exec $namespace sysctl net.ipv4.tcp_ecn=0
    echo "Disabling TCP ECN on $rx_server ..."
    ssh $rx_server "sudo ip netns exec $namespace sysctl net.ipv4.tcp_ecn=0"
fi

if [ "$(whoami)" = "raj" ]; then
    echo "Running Raj's IFTTT webhook"
    curl -X POST -H "Content-Type: application/json" -d "{\"value1\":\"${flow_size}B-${expt_name}_FCT\"}" https://maker.ifttt.com/trigger/Script_Expt_completed/with/key/gB88SULNID5Te0obIzRqK-6a-6EO6tHSSBT5ulPEBbT
elif [ "$(whoami)" = "qi" ]; then
    echo "Running Qi's IFTTT webhook"
    curl -X POST -H "Content-Type: application/json" -d "{\"value1\":\"${flow_size}B-${expt_name}_FCT\"}" https://maker.ifttt.com/trigger/notify/with/key/KaSJAeA55RPHo2JvsvAMO
fi

