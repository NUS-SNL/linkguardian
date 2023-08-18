

sudo sysctl net.core.rmem_max=8388608
sudo ip netns exec lr sysctl net.ipv4.tcp_rmem="4096 131072 8388608"

sudo sysctl -w net.core.wmem_max=16777216
sudo ip netns exec lr sysctl net.ipv4.tcp_wmem="4096 16384 16777216"



