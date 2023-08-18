#!/bin/bash

cecho(){  # source: https://stackoverflow.com/a/53463162/2886168
    RED="\033[0;31m"
    GREEN="\033[0;32m"
    YELLOW="\033[0;33m"
    # ... ADD MORE COLORS
    NC="\033[0m" # No Color

    printf "${!1}${2} ${NC}\n"
}

# Check if expt name and number is passed as an argument
if [ $# -ne 4 ];then
    cecho "YELLOW" "Usage: $0 <setup> <expt_name e.g. baseline> <congestion control algorithm to use (cubic/bbr/dctcp)> <duration in seconds>"
    exit 1
fi

# CHOOSE YOUR SETUP
setup=$1

# Setup 1
if [ $setup == 1 ]; then
    cecho "YELLOW" "######################################"
    cecho "YELLOW" "Running on setup 1: lumos <--> hajime"
    cecho "YELLOW" "######################################"
    sender_host=lumos
    receiver_host=hajime
    namespace="lr_devtest"
    sender_iface=ens2f0
    receiver_iface=enp6s0f0
    sender_cpu=2
    receiver_cpu=2
    traces_path=~/traces/linkradar/throughput
# Setup 2
elif [ $setup == 2 ]; then
    cecho "YELLOW" "###########################################"
    cecho "YELLOW" "Running on setup 2: patronus <--> knowhere"
    cecho "YELLOW" "###########################################"
    sender_host=patronus
    receiver_host=knowhere
    namespace="lr_devtest"
    sender_iface=ens3f1
    receiver_iface=ens4f1
    sender_cpu=2
    receiver_cpu=2
    traces_path=~/traces/linkradar/throughput
elif [ $setup == 3 ]; then
    cecho "YELLOW" "################################################"
    cecho "YELLOW" "Running on setup 3: lumos 100G <--> caelus 100G"
    cecho "YELLOW" "################################################"
    sender_host=lumos
    receiver_host=caelus
    namespace="lr_cx6"
    sender_iface=ens3f1
    receiver_iface=enp177s0f1
    sender_cpu=14
    receiver_cpu=18
    traces_path=~/traces/linkradar/throughput
elif [ $setup == 4 ]; then
    cecho "YELLOW" "################################################"
    cecho "YELLOW" "Running on setup 4: lumos 25G <--> caelus 25G"
    cecho "YELLOW" "################################################"
    sender_host=lumos
    receiver_host=caelus
    namespace="lr"
    sender_iface=ens2f1
    receiver_iface=ens1f1
    sender_cpu=2
    receiver_cpu=2
    traces_path=~/traces/linkradar/throughput
elif [ $setup == 5 ]; then
    cecho "YELLOW" "################################################"
    cecho "YELLOW" "Running on AE setup: lumos 10G <--> caelus 10G"
    cecho "YELLOW" "################################################"
    sender_host=lumos
    receiver_host=caelus-ae
    namespace="lg"
    sender_iface=ens3f1
    receiver_iface=enp177s0f1
    sender_cpu=2
    receiver_cpu=2
    traces_path=~/traces/throughput_expt
    cpu_power_script=/home/sigcomm23ae/linkguardian/switch_impl/expt_scripts/cpu_power_scripts/performance_mode_pstate.sh
    traces_path=~/traces/throughput_expt
else
    cecho "RED" "ERROR: unknown setup $setup"
    exit 1
fi


# Check if the script is being run on the sender host
hostname=`hostname`
if [[ "$hostname" != "$sender_host" ]];then
    cecho "RED" "ERROR: This script needs to run on $sender_host"
    exit 1
fi


expt_name=$2
cc=$3
duration=$4

# duration=100
resolution=1  # 0.1 for 100ms. 1 for 1s


# Check the congestion control algorithm
if [ "$cc" = "cubic" ] ; then
    congestion_control="cubic"
    path="cubic"
elif [ "$cc" = "bbr" ] ; then
    congestion_control="bbr"
    path="bbr"
elif [ "$cc" = "dctcp" ] ; then
    congestion_control="dctcp"
    path="dctcp"
else
    cecho "YELLOW" "ERROR: The specified congestion control algorithm is not supported by the script."
    exit 1
fi

# if [ $# -eq 2 ] || [ $# -eq 3 ] ; then
#     set_up="lr_setup1"
# else
#     set_up="lr_setup${set_up}" # avoid killing this process itself
# fi

cecho "YELLOW" "*** Running THROUGHPUT expt '$expt_name' for $congestion_control"
cecho "YELLOW" "Duration: $duration seconds"

echo "Flush TCP metrics on $sender_host ..."
sudo ip netns exec $namespace ip tcp_metrics flush
echo "Flush TCP metrics on $receiver_host ..."
ssh $receiver_host "sudo ip netns exec $namespace ip tcp_metrics flush"

if [ $setup == 1 ]; then
    echo "Switch to high performance mode on $sender_host ..."
    sudo ip netns exec $namespace sh -c "echo 'GOVERNOR=\"performance\"' > /etc/default/cpufrequtils"
    sudo ip netns exec $namespace systemctl restart cpufrequtils.service
    echo "Switch to high performance mode on $receiver_host ..."
    ssh $receiver_host "sudo ip netns exec $namespace sh -c \"echo 'GOVERNOR=\"performance\"' > /etc/default/cpufrequtils\"" 
    ssh $receiver_host "sudo ip netns exec $namespace systemctl restart cpufrequtils.service"
elif [ $setup == 3 ] || [ $setup == 4 ];then
    echo "Switch to high performance mode on $sender_host ..."
    sudo ip netns exec $namespace sh -c "echo 'GOVERNOR=\"performance\"' > /etc/default/cpufrequtils"
    sudo ip netns exec $namespace systemctl restart cpufrequtils.service
    echo "Switch to high performance mode on $receiver_host ..."
    ssh $receiver_host "/home/raj/performance_mode_pstate.sh enable" > /dev/null
elif [ $setup == 5 ]; then
    echo "Switch to high performance mode on $sender_host ..."
    sudo $cpu_power_script enable > /dev/null
    echo "Switch to high performance mode on $receiver_host ..."
    ssh $receiver_host "$cpu_power_script enable" > /dev/null
fi

echo "Setting mtu to 1500 on $sender_host ..."
sudo ip netns exec $namespace ip link set $sender_iface mtu 1500
echo "Setting mtu to 1500 on $receiver_host ..."
ssh $receiver_host "sudo ip netns exec $namespace ip link set $receiver_iface mtu 1500"

echo "Setting NIC ring buffers to maximum on $sender_host ..."
sudo ip netns exec $namespace ethtool -G $sender_iface tx 8192 rx 8192
echo "Setting NIC ring buffers to maximum on $receiver_host ..."
ssh $receiver_host "sudo ip netns exec $namespace ethtool -G $receiver_iface tx 8192 rx 8192"

echo "Disabling hardware timestamp on $sender_host ..."
sudo ip netns exec $namespace hwstamp_ctl -i $sender_iface -r 0 -t 0
echo "Disabling hardware timestamp on $receiver_host ..."
ssh $receiver_host "sudo ip netns exec $namespace hwstamp_ctl -i $receiver_iface -r 0 -t 0"

echo "Disabling TCP timestamps on $sender_host ..."
sudo ip netns exec $namespace sysctl net.ipv4.tcp_timestamps=0
echo "Disabling TCP timestamps on $receiver_host ..."
ssh $receiver_host "sudo ip netns exec $namespace sysctl net.ipv4.tcp_timestamps=0"

echo "Enabling TCP SACK on $sender_host ..."
sudo ip netns exec $namespace sysctl net.ipv4.tcp_sack=1
echo "Enabling TCP SACK on $receiver_host ..."
ssh $receiver_host "sudo ip netns exec $namespace sysctl net.ipv4.tcp_sack=1"

if [[ "$congestion_control" == "dctcp" ]] ; then
    echo "Enabling TCP ECN on $sender_host ..."
    sudo ip netns exec $namespace sysctl net.ipv4.tcp_ecn=1
    echo "Enabling TCP ECN on $receiver_host ..."
    ssh $receiver_host "sudo ip netns exec $namespace sysctl net.ipv4.tcp_ecn=1"
else
    echo "Disabling TCP ECN on $sender_host ..."
    sudo ip netns exec $namespace sysctl net.ipv4.tcp_ecn=0
    echo "Disabling TCP ECN on $receiver_host ..."
    ssh $receiver_host "sudo ip netns exec $namespace sysctl net.ipv4.tcp_ecn=0"
fi

echo "Disabling tcp_no_save on $sender_host ..."
sudo ip netns exec $namespace sysctl net.ipv4.tcp_no_metrics_save=0
echo "Disabling tcp_no_save  on $receiver_host ..."
ssh $receiver_host "sudo ip netns exec $namespace sysctl net.ipv4.tcp_no_metrics_save=0"

echo "Enabling tcp_recovery on $sender_host ..."
sudo ip netns exec $namespace sysctl net.ipv4.tcp_recovery=1
echo "Enabling tcp_recovery on $receiver_host ..."
ssh $receiver_host "sudo ip netns exec $namespace sysctl net.ipv4.tcp_recovery=1"

echo "Enabling tcp_early_retrans on $sender_host ..."
sudo ip netns exec $namespace sysctl net.ipv4.tcp_early_retrans=3
echo "Enabling tcp_early_retrans  on $receiver_host ..."
ssh $receiver_host "sudo ip netns exec $namespace sysctl net.ipv4.tcp_early_retrans=3"

echo "Setting rto_min on $sender_host ..."
sudo ip netns exec $namespace ip route change 10.2.2.0/24 via 10.2.2.1 dev $sender_iface rto_min 1ms
echo "Setting rto_min on $receiver_host ..."
ssh $receiver_host "sudo ip netns exec $namespace ip route change 10.2.2.0/24 via 10.2.2.2 dev $receiver_iface rto_min 1ms"

# TODO set initcwnd and initrwnd to 10 on both sender and receiver

echo "Creating/checking directories for storing traces"
mkdir -p $traces_path

json_file=$traces_path"/"${expt_name}-${congestion_control}.json

if [ -f $json_file ]; then
    cecho "YELLOW" "WARNING: $json_file already exists. Overwriting it."
    sudo rm $json_file
fi

echo "Sleeping 10 secs for performance mode to come into effect..."
sleep 10

cecho "YELLOW" "Starting iperf3 server on $receiver_host..."
ssh $receiver_host "sudo ip netns exec $namespace taskset --cpu-list $receiver_cpu iperf3 -s" > /dev/null &

sleep 3


cecho "YELLOW" "*** Starting flow from $sender_host..."

sudo ip netns exec $namespace taskset --cpu-list $sender_cpu iperf3 -c 10.2.2.2 -w 8M -i $resolution -J --logfile $json_file -N -t $duration -C ${congestion_control}



sleep 1

cecho "YELLOW" "*** Cleaning up"
echo "Stopping iperf3 server on $receiver_host..."
ssh $receiver_host "sudo killall -2 iperf3"

# Ensuring that tcp_ecn=0 is the default state on the servers
echo "Disabling TCP ECN on $sender_host ..."
sudo ip netns exec $namespace sysctl net.ipv4.tcp_ecn=0
echo "Disabling TCP ECN on $receiver_host ..."
ssh $receiver_host "sudo ip netns exec $namespace sysctl net.ipv4.tcp_ecn=0"

if [ $setup == 1 ]; then
    echo "Switch to moderate performance mode on $sender_host ..."
    sudo ip netns exec $namespace sh -c "echo 'GOVERNOR=\"ondemand\"' > /etc/default/cpufrequtils"
    sudo ip netns exec $namespace systemctl restart cpufrequtils.service
    echo "Switch to moderate performance mode on $receiver_host ..."
    ssh $receiver_host "sudo ip netns exec $namespace sh -c \"echo 'GOVERNOR=\"ondemand\"' > /etc/default/cpufrequtils\""
    ssh $receiver_host "sudo ip netns exec $namespace systemctl restart cpufrequtils.service"
elif [ $setup == 3 ] || [ $setup == 4 ];then 
    echo "Switch to moderate performance mode on $sender_host ..."
    sudo ip netns exec $namespace sh -c "echo 'GOVERNOR=\"ondemand\"' > /etc/default/cpufrequtils"
    sudo ip netns exec $namespace systemctl restart cpufrequtils.service
    echo "Switch to moderate performance mode on $receiver_host ..."
    ssh $receiver_host "/home/raj/performance_mode_pstate.sh disable" > /dev/null
elif [ $setup == 5 ];then 
    echo "Switch to moderate performance mode on $sender_host ..."
    sudo $cpu_power_script disable > /dev/null
    echo "Switch to moderate performance mode on $receiver_host ..."
    ssh $receiver_host "$cpu_power_script disable" > /dev/null
fi

cecho "YELLOW" "Output file:"
echo "$json_file"

if [ "$(whoami)" = "raj" ]; then
    curl -X POST -H "Content-Type: application/json" -d "{\"value1\":\"Throughput Expt\"}" https://maker.ifttt.com/trigger/Script_Expt_completed/with/key/gB88SULNID5Te0obIzRqK-6a-6EO6tHSSBT5ulPEBbT
fi
