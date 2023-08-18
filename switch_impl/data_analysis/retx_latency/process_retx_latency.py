#!/home/raj/miniconda3/envs/research/bin/python

import sys
import os
from termcolor import colored
from scapy.all import *
import numpy as np
import pandas as pd
import csv

if len(sys.argv) != 2:
    print(colored("Usage:",'yellow') + " {} <retx latency telemetry pcap file>".format(sys.argv[0]))
    sys.exit(1)

pcap_file = sys.argv[1]

outfile = os.path.splitext(pcap_file)[0] + ".dat"
outfile_cdf = os.path.splitext(pcap_file)[0] + "_cdf" + ".dat"
outfile_stats = os.path.splitext(pcap_file)[0] + "_stats" + ".dat"

print(colored("*** Processing reTx latency telemetry trace", "yellow"))
print("FROM: {}".format(pcap_file))
print("TO: {}".format(outfile), flush=True)


def add_leading_zero(hex_byte_str):
    if len(hex_byte_str) == 1:
        return '0' + hex_byte_str
    else:
        return hex_byte_str


def ip_str_to_timestamp(ip_str):
    split_str = ip_str.split('.')
    hex_str_split = [add_leading_zero(hex(int(i))[2:]) for i in split_str]
    hex_str = ''.join(hex_str_split)
    return int(hex_str, base=16)



fout = open(outfile, 'w')

count = 1 
retx_latency = np.uint32()
for pkt in PcapReader(pcap_file):
    src_ip = pkt[IP].src
    dst_ip = pkt[IP].dst
    retx_latency = np.uint32(ip_str_to_timestamp(dst_ip)) - np.uint32(ip_str_to_timestamp(src_ip))
    if retx_latency < 1000000: # 1ms
        # Unusually high retx latency due to wrapped around seq_nos can occur
        # See note: 'LinkRadar-2022_08': 
        # 'Answer to WHY sometimes we get super high ReTx latency'
        fout.write("{}\n".format(retx_latency))
    else:
        # print("High retx latency: {}: PktID: {}\tsrc_ip:{}\tdst_ip:{}".format(retx_latency, count, src_ip, dst_ip))
        pass
    count += 1


fout.close()

print("Generating CDF: {}".format(outfile_cdf), flush=True)

cdf_cmd = "getcdf {} > {}".format(outfile, outfile_cdf)
os.system(cdf_cmd)


print("Generating stats summary: {}".format(outfile_stats), flush=True)

df = pd.read_csv(outfile, header=None, names=['reTx_latency'])
df_summary = df.describe(percentiles=[.5, .9, .95, .99, .999, .9999,.99999], include='all')
df_summary = df_summary.round(3)
df_summary = df_summary.reindex(["min","mean","50%","90%","95%","99%","99.9%","99.99%","99.999%","max","std","count"])
df_summary.to_csv(outfile_stats, sep="\t", quoting=csv.QUOTE_NONE)
