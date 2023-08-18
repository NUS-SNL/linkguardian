#!/bin/bash

# on hajime
sudo tcpdump -i enp6s0f0 -s 80 -w 10G_1_percent.pcap -c 1000000 ip

# on knowhere
sudo tcpdump -i ens4f1 -s 80 -w 10G_1_percent.pcap -c 1000000 ip
