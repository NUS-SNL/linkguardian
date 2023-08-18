#!/usr/bin/env python3

import sys
import json
import os
import csv
import pandas as pd
from termcolor import colored


if len(sys.argv) != 2:
    print(colored("Usage:",'yellow') + " {} <path to iperf3 json>".format(sys.argv[0]))
    sys.exit(1)

json_file = sys.argv[1]
fin_json = open(json_file, 'r')
json_dict = json.load(fin_json)
fin_json.close()

outfile = os.path.splitext(json_file)[0] + ".dat"

df_index = ["start_time", "end_time", "bps", "retx", "cwd"]
interval_data = []  # lists of format ["start_time", "end_time", "bps", "retx", "cwd"]

for interval in json_dict["intervals"]:
    start_time = interval["streams"][0]["start"]
    end_time = interval["streams"][0]["end"]
    bps = interval["streams"][0]["bits_per_second"]
    retx = interval["streams"][0]["retransmits"]
    cwnd = interval["streams"][0]["snd_cwnd"]
    interval_data.append([start_time, end_time, bps, retx, cwnd])

df = pd.DataFrame(interval_data, columns=df_index)

df.to_csv(outfile, sep="\t", quoting=csv.QUOTE_NONE, index=False)








