#!/home/raj/miniconda3/envs/research/bin/python

import sys
import os
import csv
from termcolor import colored


# checking arguments
if len(sys.argv) != 2:
    print(colored("Usage:",'yellow') + " {} <affected parsed pkts csv file>".format(sys.argv[0]))
    sys.exit(1)

parsed_pkts_file = sys.argv[1]

outfile = os.path.splitext(parsed_pkts_file)[0] + ".dat"

print(colored("*** Processing affected flows", "yellow"))
print("FROM: {}".format(parsed_pkts_file))
print("TO: {}".format(outfile))


# Dict to track current flows
# Each flow is a dict with "time" and "pkts" as keys. 
# "time" is the time of the first pkt seen in the flow
# "pkts" is a list of pkt_info
curr_tracked_flows = {}

# List to save flows flushed from the tracked dict
# Flows would be flushed when the flow ID repeats
flushed_flows = []


# created affected flow's pkt info
def form_pkt_info(row):
    # interpret src mac address as the IPG (in ns)
    ipg = int(row[2].replace(':',''), 16)
    # interpret ipv4 ttl as the hole size
    hole_size = int(row[3])
    # tcp payload len
    tcp_payload_len = int(row[8])
    # raw seq no
    tcp_seq_no_raw = int(row[9])

    # decide the TCP packet type
    type = ''
    ack = int(row[4])
    psh = int(row[5])
    syn = int(row[6])
    fin = int(row[7])

    if psh == 1:
        type = 'PSH'
    elif syn == 1:
        type = 'SYN'
    elif fin == 1:
        type = 'FIN'
    elif ack == 1:
        if tcp_payload_len == 0:
            type = 'ACK'
        else:
            type = 'DATA'

    return (ipg, hole_size, type, tcp_seq_no_raw, tcp_payload_len)  # pkt_info

def flush_flow(flow_id):
    # pop the flow from the dict
    flow = curr_tracked_flows.pop(flow_id)
    # EXCLUDE the flow if it has a single affected pkt which is SYN
    # That's bcoz wrt FCT/sender trace analysis, the flow is NOT affected
    pkt_count = len(flow["pkts"])
    if pkt_count == 1 and flow["pkts"][0][2] == 'SYN':
        pass
    else:
        flow_entry = (flow["time"], flow_id, pkt_count, flow["pkts"])
        flushed_flows.append(flow_entry)

# flow entry: (time, flow_id, num_pkts, [pkt_info,..])
def flow_entry_to_str(flow_entry):
    pkts = flow_entry[3]
    pkt_infos = [','.join(map(str, x)) for x in pkts]
    return '\t'.join([str(flow_entry[1]), str(flow_entry[2])] + pkt_infos)

# Starting processing

fin = open(parsed_pkts_file, 'r')
csvreader = csv.reader(fin, delimiter='\t')
next(csvreader)  # read out the column header

for row in csvreader:
    flow_id = int(row[0])
    pkt_time = float(row[1])
    pkt_info = form_pkt_info(row)
    tcp_payload_len = int(row[8])
    tcp_seq_no_raw = int(row[9])

    if flow_id not in curr_tracked_flows:
        # we never saw this flow. Insert and start tracking
        pkts = [pkt_info,]
        flow_dict = {"time": pkt_time, "pkts": pkts}
        curr_tracked_flows[flow_id] = flow_dict

    else:  # flow is already seen. This is an additional affected pkt
        # add it to the pkt list of the flow
        curr_tracked_flows[flow_id]["pkts"].append(pkt_info)

# flush all the flows
remaining_flows = list(curr_tracked_flows.keys())
for flow_id in remaining_flows:
    flush_flow(flow_id)

# Sort the flushed flows by time
flushed_flows.sort(key=lambda x: x[0])

# Output the flows to the output file
fout = open(outfile, 'w')

for flow in flushed_flows:
    fout.write(flow_entry_to_str(flow)+"\n")


fin.close()
fout.close()
