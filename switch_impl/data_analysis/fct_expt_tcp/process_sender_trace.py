#!/usr/bin/env python3

import sys
import os
import csv
import math
from termcolor import colored

SENDER_IP = '10.2.2.1'
RECEIVER_IP = '10.2.2.2'

def print_usage():
    print(colored("Usage:",'yellow') + " {} <sender pkts csv file> <affected flows dat file> <flow_size_in_B> <expt_type (motivation/evaluation)> <MTU size: 1068/1500> <no_affected: 0 or 1>".format(sys.argv[0]))

# checking arguments
if len(sys.argv) != 7:
    print_usage()
    sys.exit(1)

parsed_pkts_file = sys.argv[1]
affected_flows_file = sys.argv[2]
flow_size_bytes = float(sys.argv[3])
expt_type = sys.argv[4]
MTU = int(sys.argv[5]) # 1068 or 1500
no_affected = int(sys.argv[6])


MSS_bytes = MTU - 40 # 1460

# Calculate the seq nos for tail (last 3) packets
seq_last_pkt = math.floor(flow_size_bytes / MSS_bytes) * MSS_bytes + 1
tail_pkt_seq_nos = set([seq_last_pkt, seq_last_pkt - MSS_bytes, seq_last_pkt - 2*MSS_bytes])


if expt_type not in ["motivation", "evaluation"]:
    print(colored("ERROR:",'yellow') + " Invalid expt_type {}".format(expt_type))
    print_usage()
    sys.exit(1)

if no_affected not in [0, 1]:
    print(colored("ERROR:",'yellow') + " Invalid no_affected value {}".format(no_affected))
    print_usage()
    sys.exit(1)

if MTU not in [1068, 1500]:
    print(colored("ERROR:",'yellow') + " Invalid MTU value {}".format(no_affected))
    print_usage()
    sys.exit(1)

outfile = os.path.splitext(parsed_pkts_file)[0] + ".dat"
fout = open(outfile, 'w')

# column header for the output file
fout.write("flowId\tflowSize\tfirstDataTs\tfirstAckTs\tlastDataTs\tlastAckTs\taffected\ttailPktLoss\treceivedSACK\tReTx\tmaxBif\tmaxPif\tconsecutiveLoss\n")

print(colored("*** Processing sender side trace [MTU: {}]".format(MTU), "yellow"))
print("FROM: {}".format(parsed_pkts_file))
print("TO: {}".format(outfile))
if no_affected == 0:
    print("USING: {}".format(affected_flows_file))

# Dict to track current flows
# Each flow is a dict: {"bytes_sent":0, "bytes_acked":0, "sender_fin_sent":False, "first_data_pkt_ts":-1, "first_ack_pkt_ts":-1, "last_data_pkt_ts":-1, "last_ack_pkt_ts":-1, "affected":0}
curr_tracked_flows = {}
affected_flows = []
affected_flows_without_data_loss = [] # bunch of flow IDs who didn't see data pkt loss
affected_flows_consecutive_loss = []

def check_for_consecutive_data_loss(lost_raw_seq_nos):
    num_pkts = len(lost_raw_seq_nos)
    consecutive_loss = False
    for i in range(num_pkts-1):
        curr_seq = lost_raw_seq_nos[i]
        next_seq = lost_raw_seq_nos[i+1]
        diff = next_seq - curr_seq
        if diff < 0: # handle wrap around
            diff = diff + pow(2,32)  # since 32-bit seq no
        if diff > 0 and diff <= MSS_bytes:
            consecutive_loss = True
            break
        # TODO: if diff == 0, pkt and its ReTx both got lost <== think more on this cond
    return consecutive_loss


# Loading affected flows
if no_affected == 0:
    print("Loading affected flows... ", end="")
    fin = open(affected_flows_file, 'r')
    flowreader = csv.reader(fin, delimiter='\t')
    # BUG fix: there is no column header in affected_flows.dat file
    # next(flowreader)  # read out the column header
    for row in flowreader:
        flow_id = int(row[0])

        pkt_count = int(row[1])
        data_loss_seen = 0
        data_loss_raw_seq_nos = []
        for i in range(2, 2 + pkt_count): # go over all lost pkt(s) for the flow
            # check if any of them is a data/psh pkt
            pkt_type = row[i].split(',')[2]
            if pkt_type == 'DATA' or pkt_type == 'PSH':
                data_loss_seen = 1
                raw_seq_no = int(row[i].split(',')[3])
                tcp_payload_len = int(row[i].split(',')[4])
                data_loss_raw_seq_nos.append(raw_seq_no)
                if tcp_payload_len > MSS_bytes: # consecutive loss as GRO segment in affected flows
                    affected_flows_consecutive_loss.append(flow_id)
                    
        
        if data_loss_seen == 1: # flow is indeed affected
            affected_flows.append(flow_id)
            if(len(data_loss_raw_seq_nos) > 1): # more than 1 data pkt lost
                # checking for consecutive data loss
                consecutive_loss = check_for_consecutive_data_loss(data_loss_raw_seq_nos)
                if consecutive_loss:
                    affected_flows_consecutive_loss.append(flow_id)
        else: # flow did not see any data loss
            affected_flows_without_data_loss.append(flow_id) # for debugging
    fin.close()
    print(colored("Done", 'green'), flush=True)

else: # no_affected flows is 1
    # print("NOT loading the affected flows")
    pass


# print("Filtered out flows who saw no data pkt loss: {}".format(len(affected_flows_without_data_loss)))


def is_flow_complete(flow_id):
    cond1 = (curr_tracked_flows[flow_id]["sender_fin_sent"] == True)

    bytes_sent = curr_tracked_flows[flow_id]["bytes_sent"]
    bytes_acked = curr_tracked_flows[flow_id]["bytes_acked"]
    cond2 = (bytes_acked >= bytes_sent)

    return cond1 and cond2

def flush_flow_to_output_file(flow_id):
    # pop the flow from curr_tracked_flows dict
    flow = curr_tracked_flows.pop(flow_id)
    affected = flow["affected"]
    if affected == 1 and len(affected_flows) > 0: 
    # Above cond: if flow affected & we hv collected affected_flows
    # ONLY then disambiguite between truly affected (1) vs randomly affected (2)
    # Otherwise, we simply hv to trust the trace
        if flow_id in affected_flows:       
            affected_flows.remove(flow_id)
        else:
            affected = 2
            print(colored("WARN:",'yellow') + " flow id {} is affected but NOT in affected flows list".format(flow_id))
    elif affected == 0 and expt_type == "evaluation": 
        # Not affected as per trace. BUT could be affected and handled by linkradar!
        # So mark it as affected if found in affected_flows trace
        if flow_id in affected_flows:
            affected_flows.remove(flow_id)
            affected = 1

    consecutive_loss = 0
    if affected == 1: # final verdict is that the flow is affected
        if flow_id in affected_flows_consecutive_loss: # check if faced consecutive loss
            consecutive_loss = 1
    output_row = (flow_id, flow["bytes_sent"], flow["first_data_pkt_ts"], flow["first_ack_pkt_ts"], flow["last_data_pkt_ts"], flow["last_ack_pkt_ts"], affected, flow["tailPktLoss"], flow["receivedSACK"], flow["ReTx"], flow["maxBif"], math.ceil(flow["maxBif"]/MSS_bytes), consecutive_loss)
    fout.write("\t".join(map(str, output_row)) + "\n")


def update_max_bif(flow_id):
    bif = curr_tracked_flows[flow_id]["bytes_sent"] - curr_tracked_flows[flow_id]["bytes_acked"]
    if bif > curr_tracked_flows[flow_id]["maxBif"]:
        curr_tracked_flows[flow_id]["maxBif"] = bif

def update_bytes_sent(flow_id, tcp_payload_len):
    curr_tracked_flows[flow_id]["bytes_sent"] += tcp_payload_len
    update_max_bif(flow_id)

def update_bytes_acked(flow_id, tcp_ack_no):
    curr_tracked_flows[flow_id]["bytes_acked"] = tcp_ack_no - 1
    update_max_bif(flow_id)

def compute_sacked_bytes(tcp_ack_no, tcp_sack_le, tcp_sack_re):
    # HANDLE ERRORNEOUS SACK: ack_no > the sack ranges
    max_sack_re = max(tcp_sack_re)
    if tcp_ack_no >= max_sack_re: # no bytes are actually SACK'ed
        return 0

    # form the sack ranges
    sack_ranges = []
    sacked_bytes = 0
    # TEMPORARY FIX: to handle 80 byte truncated pkt, BUT 3(!) SACK ranges (82
    # bytes)
    num_ranges = min(len(tcp_sack_le), len(tcp_sack_re))
    for i in range(num_ranges):
        sack_range = (tcp_sack_le[i], tcp_sack_re[i])
        sack_ranges.append(sack_range)
        sacked_bytes += tcp_sack_re[i] - tcp_sack_le[i]
    
    if len(sack_ranges) > 1: # more than 1 sack range
        # check for overlaps and subtract the overlapping bytes
        sack_ranges.reverse() # since SACK opts are like stack LIFO order
        for i in range(len(sack_ranges) - 1):
            prev_range = sack_ranges[i]
            next_range = sack_ranges[i+1]

            # NOTE: * operator unrolls the tuple
            prev_range_max = max(*prev_range)
            next_range_min = min(*next_range)
            if  prev_range_max > next_range_min: # overlap
                overlapped_bytes = max(*prev_range) - min(*next_range)
                sacked_bytes -= overlapped_bytes
    
    return sacked_bytes
    

def update_bytes_acked_sack(flow_id, tcp_ack_no, tcp_sack_le, tcp_sack_re):
    sacked_bytes = compute_sacked_bytes(tcp_ack_no, tcp_sack_le, tcp_sack_re)
    curr_tracked_flows[flow_id]["bytes_acked"] = (tcp_ack_no - 1) + sacked_bytes
    update_max_bif(flow_id)

# Starting processing
fin = open(parsed_pkts_file, 'r')
csvreader = csv.reader(fin, delimiter='\t')
next(csvreader)  # read out the column header

count = 0

for row in csvreader:
    count += 1
    frame_num = int(row[0])
    pkt_time = float(row[1])
    ip_src = row[2]
    ip_dst = row[3]
    src_port = int(row[4])
    dst_port = int(row[5])
    tcp_hdr_len = int(row[6])
    tcp_payload_len = int(row[7])
    tcp_seq_no = int(row[8])
    tcp_ack_no = int(row[9])
    tcp_flag_ack   = int(row[10])
    tcp_flag_push	= int(row[11])
    tcp_flag_reset	= int(row[12])
    tcp_flag_syn	= int(row[13])
    tcp_flag_fin   = int(row[14])
    tcp_seq_no_raw = int(row[15])
    
    if(row[16] != '' and row[17] != ''): # SACK LEs and REs are present
        tcp_sack_le = [int(l) for l in row[16].split(',')]
        tcp_sack_re = [int(r) for r in row[17].split(',')]

    # decide direction
    if ip_dst == RECEIVER_IP: # forward direction
        flow_id = src_port
        if tcp_flag_syn == 1 and tcp_payload_len == 0:  # starting of the new flow OR SYN reTx
            if flow_id not in curr_tracked_flows: # add the new flow
                flow = {"bytes_sent":0, "bytes_acked":0, "sender_fin_sent":False, "first_data_pkt_ts":-1, "first_ack_pkt_ts":-1, "last_data_pkt_ts":-1, "last_ack_pkt_ts":-1, "affected":0, "tailPktLoss":0, "receivedSACK":0, "ReTx":0, "maxBif":-1}
                curr_tracked_flows[flow_id] = flow
            else:
                # print(colored("WARN:",'yellow') + " SYN ReTx detected at frame {}".format(frame_num))
                pass
        elif tcp_flag_ack == 1 and tcp_flag_fin == 0 and tcp_payload_len == 0: # handshake/teardown ACK
                pass  # do nothing            
        elif tcp_flag_ack == 1 and tcp_flag_fin == 1: # FIN-ACK 
            if flow_id not in curr_tracked_flows: 
                # flow has finished but there is FIN-ACK ReTx
                pass  # ignore this FIN-ACK ReTx
            else:
                curr_tracked_flows[flow_id]["sender_fin_sent"] = True
                if tcp_payload_len > 0: # sometimes FIN can also have payload
                    # first check for re-transmission of the FIN-ACK pkt w/ payload
                    if tcp_seq_no + tcp_payload_len - 1 <= curr_tracked_flows[flow_id]["bytes_sent"]:
                        # RE-TRANSMISSION
                        # mark the flow as affected and having ReTx. That's it!
                        curr_tracked_flows[flow_id]["affected"] = 1
                        curr_tracked_flows[flow_id]["ReTx"] = 1
                    else: # normal data transmission
                        update_bytes_sent(flow_id, tcp_payload_len)
                    # update the last data pkt ts in either case
                    curr_tracked_flows[flow_id]["last_data_pkt_ts"] = pkt_time
                else: # without payload. Check if flow is complete
                    if is_flow_complete(flow_id):
                        flush_flow_to_output_file(flow_id)
        elif tcp_flag_ack == 1 and tcp_flag_fin == 0 and tcp_flag_syn == 0 and tcp_payload_len > 0:
            # DATA Packet
            if flow_id in curr_tracked_flows: # to handle spurious reTx
                if curr_tracked_flows[flow_id]["first_data_pkt_ts"] == -1: # first data pkt
                    curr_tracked_flows[flow_id]["first_data_pkt_ts"] = pkt_time
                if tcp_seq_no + tcp_payload_len - 1 <= curr_tracked_flows[flow_id]["bytes_sent"]:
                    # RE-TRANSMISSION
                    # mark the flow as affected and having ReTx. That's it!
                    curr_tracked_flows[flow_id]["affected"] = 1
                    curr_tracked_flows[flow_id]["ReTx"] = 1
                else: # normal data transmission
                    update_bytes_sent(flow_id, tcp_payload_len)
                
                # update the last data pkt ts in either case
                curr_tracked_flows[flow_id]["last_data_pkt_ts"] = pkt_time
            else:
                print(colored("WARN:",'yellow') + " unexpected DATA at frame {}".format(frame_num))
            
        else:
            print(colored("WARN:",'yellow') + " unexpected pkt at frame {}".format(frame_num))


    elif ip_dst == SENDER_IP: # reverse direction
        flow_id = dst_port

        if tcp_flag_syn == 1 and tcp_flag_ack == 1 and tcp_payload_len == 0: # SYN-ACK pkt
            pass # nothing to do
        elif tcp_flag_ack == 1 and tcp_flag_syn == 0 and tcp_flag_fin == 0 and tcp_payload_len == 0:
            # ACK pkt (could be SACK too)
            if flow_id in curr_tracked_flows: # to handle spurious ACKs
                # Check and record if it is the first ACK
                if curr_tracked_flows[flow_id]["first_ack_pkt_ts"] == -1: # first ACK
                    curr_tracked_flows[flow_id]["first_ack_pkt_ts"] = pkt_time
                
                # Update bytes acked (diff logic for SACK and normal ACK)
                if tcp_hdr_len >= 32:  # it is a SACK since larger TCP hdr
                    curr_tracked_flows[flow_id]["receivedSACK"] = 1
                    update_bytes_acked_sack(flow_id, tcp_ack_no, tcp_sack_le, tcp_sack_re)
                else:  # normal ACK
                    update_bytes_acked(flow_id, tcp_ack_no)
                
                # Update last ACK timestamp ONLY when flow_size_bytes ACK'ed
                # Do it for the FIRST time only
                if curr_tracked_flows[flow_id]["bytes_acked"] >= flow_size_bytes and curr_tracked_flows[flow_id]["last_ack_pkt_ts"] == -1:
                    curr_tracked_flows[flow_id]["last_ack_pkt_ts"] = pkt_time
    
                # Record any tail pkt loss
                if tcp_hdr_len >= 32: # it is a SACK since larger TCP hdr
                    # if tcp_ack_no == math.floor(flow_size_bytes / MSS_bytes) *
                    # MSS_bytes+ 1: # seq no of the last pkt
                    if tcp_ack_no in tail_pkt_seq_nos:
                        curr_tracked_flows[flow_id]["tailPktLoss"] = 1
                
                # Check if flow completion conditions are met
                if is_flow_complete(flow_id):
                    flush_flow_to_output_file(flow_id)
            else: # received (S)ACK for a flow that is not being tracked / flushed already
                print(colored("WARN:",'yellow') + " unexpected ACK at frame {}".format(frame_num))
        elif tcp_flag_ack == 1 and tcp_flag_syn == 0 and tcp_flag_fin == 1 and tcp_payload_len == 0:
            # FIN-ACK from receiver. Flow should be flushed at this point already
            if flow_id in curr_tracked_flows: # for some reason flow is not flushed
                # this case happens when last pkt's TCP payload is < 1460B
                # no explicit ACK is sent for this pkt
                # the FIN-ACK from the receiver acknowledges this pkt
                # print(colored("WARN:",'yellow') + " Flow has not finished at Rx FIN-ACK. Double check at frame {}".format(frame_num))
                # Update bytes acked
                update_bytes_acked(flow_id, tcp_ack_no)
                # Update last ACK timestamp
                curr_tracked_flows[flow_id]["last_ack_pkt_ts"] = pkt_time
                # try and flush the flow
                if is_flow_complete(flow_id):
                    flush_flow_to_output_file(flow_id)
                else:
                    print(colored("WARN:",'red') + " Flow didn't finish even at Rx FIN-ACK. Something is wrong at frame {}".format(frame_num))


fin.close()
fout.close()






if(len(affected_flows) > 0):
    print(colored("WARN: Remaining affected_flows: ", 'yellow') + "{}".format(len(affected_flows)))

    for flow_id in affected_flows:
        print(flow_id)

# check if there are any incomplete flows

for flow_id in curr_tracked_flows:
        print(flow_id)
if(len(curr_tracked_flows) > 0):
    print(colored("WARN: Some flows did not complete: ", 'yellow') + "{}".format(len(curr_tracked_flows)))

    for flow_id in curr_tracked_flows:
        print(flow_id)


print("Processed {} pkts in total".format(count))
