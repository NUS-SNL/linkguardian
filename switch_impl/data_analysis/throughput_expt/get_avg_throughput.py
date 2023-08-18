#!/home/raj/miniconda3/envs/research/bin/python

import sys
import pandas as pd
from termcolor import colored

if len(sys.argv) != 3:
    print(colored("Usage:",'yellow') + " {} <iperf3 parsed dat file> <intervals to skip>".format(sys.argv[0]))
    sys.exit(1)

dat_file = sys.argv[1]
num_skip_intervals = int(sys.argv[2])

df = pd.read_csv(dat_file, sep='\t')
bps_lst = list(df['bps'])
cwd_lst = list(df['cwd'])
retx_lst = list(df['retx'])
# skip the beginning intervals
bps_lst = bps_lst[num_skip_intervals:]
cwd_lst = cwd_lst[num_skip_intervals:]
retx_lst = retx_lst[num_skip_intervals:]
# find idx till the ending intervals
idx_till_last_skipped = len(bps_lst) - num_skip_intervals
# skip the ending intervals
bps_lst = bps_lst[:idx_till_last_skipped]
cwd_lst = cwd_lst[:idx_till_last_skipped]
retx_lst = retx_lst[:idx_till_last_skipped]

avg_throughput_bps = sum(bps_lst) / len(bps_lst)
avg_throughput_gbps = round(avg_throughput_bps / 1000000000, 2)

avg_cwnd_bytes = sum(cwd_lst) / len(cwd_lst)
avg_cwnd_kb = round(avg_cwnd_bytes / 1000, 2)

total_retx = sum(retx_lst)
avg_retx = total_retx / len(retx_lst)

# print("{} ({})".format(avg_throughput_gbps, avg_cwnd_kb))
print("Avg Throughput: {}".format(avg_throughput_gbps))
# print("Avg ReTx: {}".format(avg_retx))
# print("Total ReTx: {}".format(total_retx))
