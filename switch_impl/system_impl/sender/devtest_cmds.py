from builtins import KeyboardInterrupt
from cgitb import handler
import random
import time
import socket
import math
import subprocess
import os
import threading
from tabulate import tabulate

TX_MULTICAST_GRPS_BUFFERED_PKTS_START = 1 # MUST be same as in sender/setup.py 

TX_BUFFER_DATA_DUMP_PATH = '/home/cirlab/traces/effective_lossRate_linkSpeed'

python3_interpreter = '/usr/bin/python3'
rx_ok_counter_script = '/home/cirlab/jarvis-tofino/linkradar/system_impl/sender/get_rx_ok_counter.py'
rx_forwarded_counter_script = '/home/cirlab/jarvis-tofino/linkradar/expt_scripts/effective_lossRate_linkSpeed/get_rx_forwarded_counter.py'

ssh_alias_rx_switch = "tofino1c"
ssh_alias_topo_switch = "p4campus-proc1"
sde_install_on_rx = '/home/cirlab/bf-sde-9.9.0/install'
poll_rx_counters_script_on_rx = '/home/cirlab/jarvis-tofino/linkradar/expt_scripts/effective_lossRate_linkSpeed/poll_rx_counters.py'

devports_to_check = {16:"tx_recirc_buff", 
                     32:"protected_link_tx", 
                     36:"large_topo_tofino1b_conn",
                     60: "iperf_sender_patronus",
                     68: "pipe0_recirc_mirror",
                     132: "iperf_sender_lumos"
                    }


stop_polling_tx_buffer = threading.Event()
tx_buff_polling_thread = None

# CHECK_LOSS_RATE_MAX_PKTS = 1000000000
NUMBER_100M = 100000000
NUMBER_1B = 1000000000
# NUMBER_10B = 10000000000  # wrap around issue with 32-bit counter
NUMBER_4B = 4000000000
NUMBER_2B = 2000000000

TX_DEV_PORT = 32
RX_DEV_PORT = 36
RX_FILTER_DEV_PORT = 44
RECIRC_LPBK_PORT = 16


# DCQCN
DCQCN_K_MIN = 1250 # 100KB - 1250
DCQCN_K_MAX = 3000 # 240KB  # 400KB - 5000
DCQCN_P_MAX = 0.2 # 20%
QDEPTH_RANGE_MAX = 2**19
SEED_RANGE_MAX = 256 # random number range ~ [0, 255] (8bits)
SEED_K_MAX = math.ceil(DCQCN_P_MAX * SEED_RANGE_MAX) # 52
QDEPTH_STEPSIZE = math.floor((DCQCN_K_MAX - DCQCN_K_MIN) / SEED_K_MAX) # 72
last_range = DCQCN_K_MIN
dcqcn_get_ecn_probability = bfrt.sender.pipe.SwitchEgress.dcqcn_get_ecn_probability # table 


host = socket.gethostname()

def get_pg_id(dev_port):
    # each pipe has 128 dev_ports + divide by 4 to get the pg_id
    pg_id = (dev_port % 128) >> 2 
    return pg_id

def get_pg_queue(dev_port, qid):
    lane = dev_port % 4
    pg_queue = lane * 8 + qid # there are 8 queues per lane
    return pg_queue

if host == 'hep':
    DEVTEST_DIR = "/home/tofino/jarvis-tofino/linkradar/system_impl/devtest"
else:
    DEVTEST_DIR = "/home/cirlab/jarvis-tofino/linkradar/system_impl/devtest"


reg_seq_no = bfrt.sender.pipe.SwitchEgress.reg_seq_no
reg_era = bfrt.sender.pipe.SwitchEgress.reg_era
reg_corruption_seq_no = bfrt.sender.pipe.SwitchEgress.reg_corruption_seq_no
emulate_corruption = bfrt.sender.pipe.SwitchEgress.emulate_corruption
decide_to_emulate_corruption = bfrt.sender.pipe.SwitchEgress.decide_to_emulate_corruption
reg_leading_ack = bfrt.sender.pipe.SwitchIngress.reg_leading_ack
reg_leading_ack_era = bfrt.sender.pipe.SwitchIngress.reg_leading_ack_era
reg_pktgen_cntr = bfrt.sender.pipe.SwitchIngress.reg_pktgen_cntr
limit_pktgen_traffic = bfrt.sender.pipe.SwitchIngress.limit_pktgen_traffic
reg_buffered_pkts_eg_stats = bfrt.sender.pipe.SwitchEgress.reg_buffered_pkts_eg_stats
reg_ig_debug_counter = bfrt.sender.pipe.SwitchIngress.reg_debug_counter
reg_eg_debug_counter = bfrt.sender.pipe.SwitchEgress.reg_debug_counter

link_protect = bfrt.sender.pipe.SwitchEgress.link_protect
copy_pkt_for_buffering = bfrt.sender.pipe.SwitchEgress.copy_pkt_for_buffering

reg_dummy_pkt_notify_count = bfrt.sender.pipe.SwitchEgress.reg_dummy_pkt_notify_count

reg_debug_index = bfrt.sender.pipe.SwitchIngress.reg_debug_index
reg_debug_value = bfrt.sender.pipe.SwitchIngress.reg_debug_value

era_correction = bfrt.sender.pipe.SwitchIngress.era_correction
decide_retx_or_drop = bfrt.sender.pipe.SwitchIngress.decide_retx_or_drop
retx_mcast_buffered_pkt = bfrt.sender.pipe.SwitchIngress.retx_mcast_buffered_pkt
reg_holes_1 = bfrt.sender.pipe.SwitchIngress.reg_holes_1
reg_holes_2 = bfrt.sender.pipe.SwitchIngress.reg_holes_2
reg_holes_3 = bfrt.sender.pipe.SwitchIngress.reg_holes_3
reg_holes_4 = bfrt.sender.pipe.SwitchIngress.reg_holes_4
reg_holes_5 = bfrt.sender.pipe.SwitchIngress.reg_holes_5

reg_emulated_corruption_counter = bfrt.sender.pipe.SwitchEgress.reg_emulated_corruption_counter

reg_ecn_marking_threshold = bfrt.sender.pipe.SwitchEgress.reg_ecn_marking_threshold

reg_circulating_era_0 = bfrt.sender.pipe.SwitchIngress.reg_circulating_era_0
reg_circulating_era_1 = bfrt.sender.pipe.SwitchIngress.reg_circulating_era_1
reg_lack_hole_records_idx = bfrt.sender.pipe.SwitchIngress.reg_lack_hole_records_idx
reg_lack_hole_records = bfrt.sender.pipe.SwitchIngress.reg_lack_hole_records
reg_buffered_dropped_records_idx = bfrt.sender.pipe.SwitchIngress.reg_buffered_dropped_records_idx
reg_buffered_dropped_records = bfrt.sender.pipe.SwitchIngress.reg_buffered_dropped_records

eg_debug_counter = bfrt.sender.pipe.SwitchEgress.eg_debug_counter
eg_debug_counter2 = bfrt.sender.pipe.SwitchEgress.eg_debug_counter2

tbl_tm_eg_counter = bfrt.tf1.tm.counter.eg_port

def start_traffic():
    # toggle_pktgen.set_default_with_nop()
    bfrt.tf1.pktgen.app_cfg.mod_with_trigger_timer_periodic(app_id=1, app_enable=True)


def stop_traffic():
    # toggle_pktgen.set_default_with_drop()
    bfrt.tf1.pktgen.app_cfg.mod_with_trigger_timer_periodic(app_id=1, app_enable=False)

def reset_trafficgen_counter():
    reg_pktgen_cntr.clear()

def get_tx_all():
    return bfrt.port.port_stat.get(DEV_PORT=TX_DEV_PORT, print_ents=0).data[b'$FramesTransmittedAll']

def get_sent_for_tx_buffering():
    pkts_sent_for_eg_mirror = reg_buffered_pkts_eg_stats.get(REGISTER_INDEX=0,
    from_hw=True,print_ents=False).data[b'SwitchEgress.reg_buffered_pkts_eg_stats.f1'][0]
    return pkts_sent_for_eg_mirror
    # pkts_succesfully_eg_mirrored = eg_debug_counter2.get(COUNTER_INDEX=0, from_hw=1, print_ents=0).data[b'$COUNTER_SPEC_PKTS']
    # return pkts_succesfully_eg_mirrored
    

def reset_all():
    bfrt.port.port_stat.clear()
    stop_traffic()
    reg_seq_no.clear()
    reg_era.clear()
    reg_corruption_seq_no.clear()
    reg_ig_debug_counter.clear()
    reg_eg_debug_counter.clear()
    reg_leading_ack.clear()
    reg_leading_ack_era.clear()
    reg_ig_debug_counter.clear()
    reg_eg_debug_counter.clear()
    reg_emulated_corruption_counter.clear()
    reg_lack_hole_records_idx.clear()
    reg_lack_hole_records.clear()
    reg_dummy_pkt_notify_count.clear()
    reg_pktgen_cntr.clear()
    reg_buffered_pkts_eg_stats.clear()
    reg_holes_1.clear()
    reg_holes_2.clear()
    reg_holes_3.clear()
    reg_holes_4.clear()
    reg_holes_5.clear()
    eg_debug_counter.clear()
    eg_debug_counter2.clear()
    clear_buffer_peak_usage()
    clear_tm_egress_port_drops()

def clear_all_emulated_holes():
    emulate_corruption.clear()

def check_sender_state(eg_port=TX_DEV_PORT):
    next_seq_no = reg_seq_no.get(REGISTER_INDEX=eg_port, print_ents=False, from_hw=True).data[b'SwitchEgress.reg_seq_no.f1'][0]
    next_seq_era = reg_era.get(REGISTER_INDEX=eg_port, print_ents=False, from_hw=True).data[b'SwitchEgress.reg_era.f1'][0]
    leading_ack = reg_leading_ack.get(REGISTER_INDEX=eg_port, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_leading_ack.f1'][0]
    leading_ack_era = reg_leading_ack_era.get(REGISTER_INDEX=eg_port, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_leading_ack_era.f1'][0]
    ig_debug_counter = reg_ig_debug_counter.get(REGISTER_INDEX=0, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_debug_counter.f1'][0]
    eg_debug_counter = reg_eg_debug_counter.get(REGISTER_INDEX=0, from_hw=True, print_ents=False).data[b'SwitchEgress.reg_debug_counter.f1'][0]
    emulated_corruption_counter = reg_emulated_corruption_counter.get(REGISTER_INDEX=0, from_hw=True, print_ents=False).data[b'SwitchEgress.reg_emulated_corruption_counter.f1'][0]
    corruption_seq_no = reg_corruption_seq_no.get(REGISTER_INDEX=32, from_hw=True, print_ents=False).data[b'SwitchEgress.reg_corruption_seq_no.f1'][0]
    cells = reg_ecn_marking_threshold.get(REGISTER_INDEX=0, from_hw=True, print_ents=False).data[b'SwitchEgress.reg_ecn_marking_threshold.f1'][1]
    ecn_threshold_kb = (cells * 80) / 1000

    print("Next seq no:", next_seq_no)
    print("Next seq era:", next_seq_era)
    print("leading_ack:", leading_ack)
    print("leading_ack_era:", leading_ack_era)
    print("ig_debug_counter:", ig_debug_counter)
    print("eg_debug_counter:", eg_debug_counter)
    print("")
    print("corruption_seq_no (egress pkt counter):", corruption_seq_no)
    print("emulated_corruption_counter (pkts dropped):", emulated_corruption_counter)

    total_pkts_to_corrupt = emulate_corruption.info(return_info=True, print_info=False)['usage']
    print("Emulated holes: {}".format(total_pkts_to_corrupt), end="")

    corrupting_ports = []
    total_ports_to_corrupt = decide_to_emulate_corruption.info(return_info=True, print_info=False)['usage']
    for hdl in range(2, total_ports_to_corrupt+2):
        port = decide_to_emulate_corruption.get(handle=hdl, print_ents=False).key[b'eg_intr_md.egress_port[7:0]']
        corrupting_ports.append(port)
    print("Corrupting Port(s) ({}): {}".format(total_ports_to_corrupt, ", ".join([str(i) for i in corrupting_ports])), end="")
    
    protected_ports = []
    total_ports_to_protect = link_protect.info(return_info=True, print_info=False)['usage']
    for hdl in range(2, total_ports_to_protect+2):
        port = link_protect.get(handle=hdl, print_ents=False).key[b'eg_intr_md.egress_port']
        mode = link_protect.get(handle=hdl, print_ents=False).data[b'blocking_mode']
        protected_ports.append((port, mode))
    print("Protected Port(s) ({}): {}".format(total_ports_to_protect, ", ".join(["{}({})".format(str(i[0]), str(i[1])) for i in protected_ports])), end="")
    print("\nNo. of reTx copies: {}".format(get_number_of_retx_copies()))
    print("\nECN Marking Threshold: {}KB ({} cells)".format(ecn_threshold_kb, cells))


emulated_holes = []
def get_emulated_holes():
    total_pkts_to_corrupt = emulate_corruption.info(return_info=True, print_info=False)['usage']
    print("Emulated holes: {}".format(total_pkts_to_corrupt))
    for hdl in range(2,total_pkts_to_corrupt+2):
        seq_no = emulate_corruption.get(handle=hdl, print_ents=False).key[b'eg_meta.corruption_seq_no']
        emulated_holes.append(seq_no)


def mark_for_corruption(s):
    emulate_corruption.add_with_corrupt(corruption_seq_no=s)

def emulate_random_losses(loss_rate_frac):
    """
    Uniformly randomly selects seq_nos to mark for corruption.
    Excludes zero though. Hole size of 1. Also logs the holes to "emulated_holes.dat".

    loss_rate_frac: loss rate expresses as a fraction. 
                    e.g. 1% ==> 0.01
    """
    num_holes = int(loss_rate_frac * 65536)
    holes = set()
    fout = open(DEVTEST_DIR + "/emulated_holes.dat", "w")
    count = 0

    while(count != num_holes):
        candidate_hole = random.randint(1, 65450)
        if (candidate_hole-1) in holes or candidate_hole in holes or (candidate_hole+1) in holes:
            continue
        else:
            holes.add(candidate_hole)
            count += 1
    for h in sorted(holes):
        mark_for_corruption(h)
        fout.write("{}\n".format(h))
        
    print("Emulated holes = {}".format(len(holes)))
    fout.close()

def emulate_fixed_random_losses():
    fin = open(DEVTEST_DIR + "/fixed_emulated_holes.dat", "r")
    holes_count = 0
    for line in fin:
        hole = int(line.strip())
        mark_for_corruption(hole)
        holes_count += 1
    print("Emulated fixed holes = {}".format(holes_count))
    fin.close()



def get_buffered_pkt_stats():
    pkts_sent_for_eg_mirror = reg_buffered_pkts_eg_stats.get(REGISTER_INDEX=0, from_hw=True, print_ents=False).data[b'SwitchEgress.reg_buffered_pkts_eg_stats.f1'][0]

    # below involved reg got into multi-stage allocation with 9.10.0
    # pkts_succesfully_eg_mirrored = reg_buffered_pkts_eg_stats.get(REGISTER_INDEX=1, from_hw=True, print_ents=False).data[b'SwitchEgress.reg_buffered_pkts_eg_stats.f1'][0]

    pkts_succesfully_eg_mirrored = eg_debug_counter2.get(COUNTER_INDEX=0, from_hw=1, print_ents=0).data[b'$COUNTER_SPEC_PKTS']
    
    pkts_dropped = decide_retx_or_drop.get(is_missing_hole_1=0,is_missing_hole_1_mask=1, is_missing_hole_2=0, is_missing_hole_2_mask=1, is_missing_hole_3=0, is_missing_hole_3_mask=1, is_missing_hole_4=0, is_missing_hole_4_mask=1, is_missing_hole_5=0, is_missing_hole_5_mask=1, MATCH_PRIORITY=5, from_hw=True, print_ents=False).data[b'$COUNTER_SPEC_PKTS']
    
    pkts_retx_hole_1 = decide_retx_or_drop.get(is_missing_hole_1=1,is_missing_hole_1_mask=1, is_missing_hole_2=0, is_missing_hole_2_mask=0, is_missing_hole_3=0, is_missing_hole_3_mask=0, is_missing_hole_4=0, is_missing_hole_4_mask=0, is_missing_hole_5=0, is_missing_hole_5_mask=0,MATCH_PRIORITY=0, from_hw=True, print_ents=False).data[b'$COUNTER_SPEC_PKTS']

    pkts_retx_hole_2 = decide_retx_or_drop.get(is_missing_hole_1=0,is_missing_hole_1_mask=0, is_missing_hole_2=1, is_missing_hole_2_mask=1, is_missing_hole_3=0, is_missing_hole_3_mask=0, is_missing_hole_4=0, is_missing_hole_4_mask=0, is_missing_hole_5=0, is_missing_hole_5_mask=0,MATCH_PRIORITY=1, from_hw=True, print_ents=False).data[b'$COUNTER_SPEC_PKTS']

    pkts_retx_hole_3 = decide_retx_or_drop.get(is_missing_hole_1=0,is_missing_hole_1_mask=0, is_missing_hole_2=0, is_missing_hole_2_mask=0, is_missing_hole_3=1, is_missing_hole_3_mask=1, is_missing_hole_4=0, is_missing_hole_4_mask=0, is_missing_hole_5=0, is_missing_hole_5_mask=0,MATCH_PRIORITY=2, from_hw=True, print_ents=False).data[b'$COUNTER_SPEC_PKTS']

    pkts_retx_hole_4 = decide_retx_or_drop.get(is_missing_hole_1=0,is_missing_hole_1_mask=0, is_missing_hole_2=0, is_missing_hole_2_mask=0, is_missing_hole_3=0, is_missing_hole_3_mask=0, is_missing_hole_4=1, is_missing_hole_4_mask=1, is_missing_hole_5=0, is_missing_hole_5_mask=0,MATCH_PRIORITY=3, from_hw=True, print_ents=False).data[b'$COUNTER_SPEC_PKTS']

    pkts_retx_hole_5 = decide_retx_or_drop.get(is_missing_hole_1=0,is_missing_hole_1_mask=0, is_missing_hole_2=0, is_missing_hole_2_mask=0, is_missing_hole_3=0, is_missing_hole_3_mask=0, is_missing_hole_4=0, is_missing_hole_4_mask=0, is_missing_hole_5=1, is_missing_hole_5_mask=1,MATCH_PRIORITY=4, from_hw=True, print_ents=False).data[b'$COUNTER_SPEC_PKTS']

    # pkts_dropped = decide_retx_or_drop.get(is_missing_hole_1=0,is_missing_hole_1_mask=1,  MATCH_PRIORITY=1, from_hw=True, print_ents=False).data[b'$COUNTER_SPEC_PKTS']
    
    # pkts_retx_hole_1 = decide_retx_or_drop.get(is_missing_hole_1=1,is_missing_hole_1_mask=1, MATCH_PRIORITY=0, from_hw=True, print_ents=False).data[b'$COUNTER_SPEC_PKTS']
    
    print("Pkts sent for eg mirroring: {}".format(pkts_sent_for_eg_mirror))
    print("Pkts successfully eg mirrored: {}".format(pkts_succesfully_eg_mirrored))
    print("Buffered pkts dropped: {}".format(pkts_dropped))
    print("Buffered pkts reTx (hole_1): {}".format(pkts_retx_hole_1))
    print("Buffered pkts reTx (hole_2): {}".format(pkts_retx_hole_2))
    print("Buffered pkts reTx (hole_3): {}".format(pkts_retx_hole_3))
    print("Buffered pkts reTx (hole_4): {}".format(pkts_retx_hole_4))
    print("Buffered pkts reTx (hole_5): {}".format(pkts_retx_hole_5))
    print("Total dropped + ReTx: {}".format(pkts_dropped + pkts_retx_hole_1 + pkts_retx_hole_2 + pkts_retx_hole_3 + pkts_retx_hole_4 + pkts_retx_hole_5))


def get_recirculating_pkts():
    era_0_pkts = []
    era_1_pkts = []

    # First, clear the two registers to get fresh recirculating bits
    reg_circulating_era_0.clear()
    reg_circulating_era_1.clear()

    # Sleep to allow fresh setting of the bits
    time.sleep(2)

    # Now read the registers
    for i in range(65536):
        bit_era0 = reg_circulating_era_0.get(REGISTER_INDEX=i, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_circulating_era_0.f1'][0]
        bit_era1 = reg_circulating_era_1.get(REGISTER_INDEX=i, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_circulating_era_1.f1'][0]
        
        if bit_era0 == 1:
            era_0_pkts.append(i)
        if bit_era1 == 1:
            era_1_pkts.append(i)

    print("Era 0 pkts ({}):\n{}".format(len(era_0_pkts), ' '.join(map(str, era_0_pkts))))
    print("Era 1 pkts ({}):\n{}".format(len(era_1_pkts), ' '.join(map(str, era_1_pkts))))


def get_index_and_value():
    index = reg_debug_index.get(REGISTER_INDEX=0, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_debug_index.f1'][0]
    value = reg_debug_value.get(REGISTER_INDEX=0, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_debug_value.f1'][0]
    print("Index: ", index)
    print("Value: ", value)

marked_holes_1 = []
marked_holes_2 = []
marked_holes_3 = []
marked_holes_4 = []
marked_holes_5 = []

def get_marked_holes():
    global marked_holes_1
    global marked_holes_2
    global marked_holes_3
    global marked_holes_4
    global marked_holes_5
    marked_holes_1 = []
    marked_holes_2 = []
    marked_holes_3 = []
    marked_holes_4 = []
    marked_holes_5 = []

    for i in range(65536):
        hole_mark_1 = reg_holes_1.get(REGISTER_INDEX=i, from_hw=True, print_ents=False).data[b"SwitchIngress.reg_holes_1.f1"][0]
        if(hole_mark_1 == 1):
            marked_holes_1.append(i)
        
        hole_mark_2 = reg_holes_2.get(REGISTER_INDEX=i, from_hw=True, print_ents=False).data[b"SwitchIngress.reg_holes_2.f1"][0]
        if(hole_mark_2 == 1):
            marked_holes_2.append(i)

        hole_mark_3 = reg_holes_3.get(REGISTER_INDEX=i, from_hw=True, print_ents=False).data[b"SwitchIngress.reg_holes_3.f1"][0]
        if(hole_mark_3 == 1):
            marked_holes_3.append(i)

        hole_mark_4 = reg_holes_4.get(REGISTER_INDEX=i, from_hw=True, print_ents=False).data[b"SwitchIngress.reg_holes_4.f1"][0]
        if(hole_mark_4 == 1):
            marked_holes_4.append(i)

        hole_mark_5 = reg_holes_5.get(REGISTER_INDEX=i, from_hw=True, print_ents=False).data[b"SwitchIngress.reg_holes_5.f1"][0]
        if(hole_mark_5 == 1):
            marked_holes_5.append(i)

def show_marked_holes():
    print("holes_1: ", end="")
    print(" ".join(map(str, marked_holes_1)))
    print("holes_2: ", end="")
    print(" ".join(map(str, marked_holes_2)))
    print("holes_3: ", end="")
    print(" ".join(map(str, marked_holes_3)))
    print("holes_4: ", end="")
    print(" ".join(map(str, marked_holes_4)))
    print("holes_5: ", end="")
    print(" ".join(map(str, marked_holes_5)))


def clear_marked_holes():
    reg_holes_1.clear()
    reg_holes_2.clear()
    reg_holes_3.clear()
    reg_holes_4.clear()
    reg_holes_5.clear()


lack_hole_records = []
def get_lack_hole_records():
    num_entries = reg_lack_hole_records_idx.get(REGISTER_INDEX=0, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_lack_hole_records_idx.f1'][0]
    print("Fetching {} records... ".format(num_entries), flush=True)
    for i in range(num_entries):
        lack = reg_lack_hole_records.get(REGISTER_INDEX=i, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_lack_hole_records.lack'][0]
        hole_1 = reg_lack_hole_records.get(REGISTER_INDEX=i, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_lack_hole_records.first_lost_seq_no'][0]
        lack_hole_records.append((lack, hole_1))

buffered_dropped_records = []
def get_buffered_dropped_records():
    num_entries = reg_buffered_dropped_records_idx.get(REGISTER_INDEX=0, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_buffered_dropped_records_idx.f1'][0]
    print("Fetching {} records... ".format(num_entries), flush=True)
    for i in range(num_entries):
        curr_lack = reg_buffered_dropped_records.get(REGISTER_INDEX=i, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_buffered_dropped_records.curr_lack'][0]
        buffered_seq_no = reg_buffered_dropped_records.get(REGISTER_INDEX=i, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_buffered_dropped_records.buffered_seq_no'][0]
        buffered_dropped_records.append((curr_lack, buffered_seq_no))


def disable_protection(devport):
    try:
        link_protect.delete(egress_port=devport)
    except Exception as e:
        # print(e)
        print("WARN: Protection not enabled on port {}!".format(devport))

def enable_protection(devport, mode=0):
    try:
        link_protect.add_with_protect(egress_port=devport, dummy_pkt_max_count=3, blocking_mode=mode)
    except Exception as e:
        entry = link_protect.get(egress_port=32, print_ents=False)
        if entry.data[b'blocking_mode'] == mode:
            print("WARN: Protection already enabled on port {}!".format(devport))
        else:
            disable_protection(devport)
            link_protect.add_with_protect(egress_port=devport, dummy_pkt_max_count=3, blocking_mode=mode)

def enable_corruption(devport):
    decide_to_emulate_corruption.add_with_mark_for_corruption_emulation(egress_port_7_0_=devport, seqno_lookup_idx=devport)

def disable_corruption(devport):
    decide_to_emulate_corruption.delete(egress_port_7_0_=devport)


# 100KB for 10Gbps and 30KB for 1Gbps
# Src: https://www.kernel.org/doc/html/latest/networking/dctcp.html
def set_ecn_marking_threshold(threshold_kb=100): 
    cells = math.ceil((threshold_kb * 1000)/80)
    reg_ecn_marking_threshold.mod(REGISTER_INDEX=0, f1=cells)

def remove_ecn_marking_threshold():
    reg_ecn_marking_threshold.clear()


def get_buffer_peak_usage():
    # Tx buffering ports
    buffer_peak_recirc = bfrt.tf1.tm.counter.queue.get(pg_id=get_pg_id(68), pg_queue=0, pipe=0, print_ents=0).data[b'watermark_cells']
    buffer_peak_lpbk = bfrt.tf1.tm.counter.queue.get(pg_id=get_pg_id(RECIRC_LPBK_PORT), pg_queue=0, pipe=0, print_ents=0).data[b'watermark_cells']

    buffer_peak_protected_link_tx = bfrt.tf1.tm.counter.queue.get(pg_id=get_pg_id(TX_DEV_PORT), pg_queue=0, pipe=0, print_ents=0).data[b'watermark_cells']

    buffer_peak_iperf_sender_port_lumos = bfrt.tf1.tm.counter.queue.get(pg_id=get_pg_id(132), pg_queue=0, pipe=0, print_ents=0).data[b'watermark_cells']

    buffer_peak_iperf_sender_port_patronus = bfrt.tf1.tm.counter.queue.get(pg_id=get_pg_id(60), pg_queue=0, pipe=0, print_ents=0).data[b'watermark_cells']

    print("Tx buffering: ({},{})".format(buffer_peak_recirc, buffer_peak_lpbk))
    print("Protected Link Tx: {}".format(buffer_peak_protected_link_tx))
    print("iperf sender port (lumos): {}".format(buffer_peak_iperf_sender_port_lumos))
    print("iperf sender port (patronus): {}".format(buffer_peak_iperf_sender_port_patronus))
    return 

def clear_buffer_peak_usage():
    bfrt.tf1.tm.counter.queue.clear()


def get_rx_ok_counter(rand_drop=False):
    if rand_drop:
        rx_devport = RX_FILTER_DEV_PORT
    else:
        rx_devport = RX_DEV_PORT
    output = subprocess.check_output([python3_interpreter, rx_ok_counter_script, str(rx_devport)])
    rx_ok = int(output.decode("utf-8").strip())
    return rx_ok

def get_rx_forwarded_counter(nb_mode):
    if nb_mode:
        nb_mode_arg = 1
    else:
        nb_mode_arg = 0
    output = subprocess.check_output([python3_interpreter, rx_forwarded_counter_script, str(nb_mode_arg)])
    rx_forwarded = int(output.decode("utf-8").strip())
    return rx_forwarded

def check_loss_rate(num_pkts=NUMBER_100M):
    stop_traffic() # if any
    try:
        disable_protection(TX_DEV_PORT) # if any
    except:
        pass
    limit_pktgen_traffic.set_default_with_nop()
    reset_trafficgen_counter()

    # Clear port counters on both sides
    bfrt.port.port_stat.clear()
    input("Clear port counters on RX switch and press enter...")
    start_traffic()

    pkts_sent = 0
    while pkts_sent < num_pkts:
        pkts_sent = get_tx_all()
        print("{} ".format(pkts_sent), end="", flush=True)
        time.sleep(1)

    stop_traffic()

    time.sleep(2)

    rx_ok = get_rx_ok_counter()
    tx_all = get_tx_all()
    # bfrt.port.port_stat.get(DEV_PORT=32, print_ents=0).data[b'$FramesTransmittedAll']

    flr = (tx_all - rx_ok)/tx_all

    limit_pktgen_traffic.set_default_with_check_pktgen_cntr_and_drop()
    reset_trafficgen_counter()

    print("\nFLR: {:e}".format(flr))

def limit_trafficgen():
    limit_pktgen_traffic.set_default_with_check_pktgen_cntr_and_drop()

def unlimit_trafficgen():
    limit_pktgen_traffic.set_default_with_nop()

def get_mode_counters():
    nb_count = eg_debug_counter.get(COUNTER_INDEX=0, from_hw=1, print_ents=0).data[b'$COUNTER_SPEC_PKTS']
    b_count = eg_debug_counter.get(COUNTER_INDEX=1, from_hw=1, print_ents=0).data[b'$COUNTER_SPEC_PKTS']

    print("NB mode: {}".format(nb_count))
    print("B mode: {}".format(b_count))

def get_tm_egress_port_drops():
    global devports_to_check
    tbl_tm_eg_counter = bfrt.tf1.tm.counter.eg_port

    tm_eg_port_drops = []

    for devport in devports_to_check:
        eg_drops = tbl_tm_eg_counter.get(dev_port=devport, print_ents=False, from_hw=True).data[b'drop_count_packets']
        tm_eg_port_drops.append([devport, devports_to_check[devport],eg_drops])
    
    print(tabulate(tm_eg_port_drops))

    

def clear_tm_egress_port_drops():
    global devports_to_check
    tbl_tm_eg_counter = bfrt.tf1.tm.counter.eg_port
    # tbl_tm_eg_counter.clear() # doesn't work with SDE 9.10.0
    for devport in devports_to_check:
        tbl_tm_eg_counter.mod(dev_port=devport, drop_count_packets=0, watermark_cells=0)


def reconfig_dcqcn_ecn_threshold(Kmin:int, Kmax: int, Pmax: float):
    DCQCN_K_MIN = Kmin
    DCQCN_K_MAX = Kmax
    DCQCN_P_MAX = Pmax
    SEED_K_MAX = math.ceil(DCQCN_P_MAX * SEED_RANGE_MAX)
    QDEPTH_STEPSIZE = math.floor((DCQCN_K_MAX - DCQCN_K_MIN) / SEED_K_MAX)
    last_range = DCQCN_K_MIN
    dcqcn_get_ecn_probability = bfrt.sender.pipe.SwitchEgress.dcqcn_get_ecn_probability
    dcqcn_compare_probability = bfrt.sender.pipe.SwitchEgress.dcqcn_compare_probability

    #####################
    # PROBABILITY TABLE #
    #####################
    # clear table
    print("Clear DCQCN ECN marking / comparing table...")
    dcqcn_get_ecn_probability.clear()
    dcqcn_compare_probability.clear()

    print("Reconfigure DCQCN ECN marking table...")
    # print("DCQCN Table -- Adding qdepth:[{}, {}] -> probability:{:.2f}% ({}/{})".format(0, DCQCN_K_MIN - 1, float(0/SEED_RANGE_MAX)*100, 0, SEED_RANGE_MAX))
    dcqcn_get_ecn_probability.add_with_dcqcn_mark_probability(deq_qdepth_start=0, deq_qdepth_end=DCQCN_K_MIN - 1, value=0)
    # K_MIN < qDepth < K_MAX
    for i in range(1, SEED_K_MAX):
        # print("DCQCN Table -- Adding qdepth:[{}, {}] -> probability:{:.2f}% ({}/{})".format(last_range, last_range + QDEPTH_STEPSIZE - 1, float(i/SEED_RANGE_MAX)*100, i, SEED_RANGE_MAX))
        dcqcn_get_ecn_probability.add_with_dcqcn_mark_probability(deq_qdepth_start=last_range, deq_qdepth_end=last_range + QDEPTH_STEPSIZE - 1, value=i)
        last_range += QDEPTH_STEPSIZE
    # > K_MAX
    # print("DCQCN Table -- Adding qdepth:[{}, {}] -> probability:{:.2f}%".format(last_range, QDEPTH_RANGE_MAX - 1, float(SEED_RANGE_MAX/SEED_RANGE_MAX)*100))
    dcqcn_get_ecn_probability.add_with_dcqcn_mark_probability(deq_qdepth_start=last_range, deq_qdepth_end=QDEPTH_RANGE_MAX - 1, value=SEED_RANGE_MAX - 1)

    ####################
    # COMPARISON TABLE #
    ####################
    # Less than 100%
    for prob_output in range(1, SEED_K_MAX): 
        for random_number in range(SEED_RANGE_MAX): # 0 ~ 255
            if random_number < prob_output:
                # print("Comparison Table -- ECN Marking for Random Number {}, Output Value {}".format(random_number, prob_output))
                bfrt.sender.pipe.SwitchEgress.dcqcn_compare_probability.add_with_dcqcn_check_ecn_marking(dcqcn_prob_output=prob_output, dcqcn_random_number=random_number)
    # 100% ECN Marking
    for random_number in range(SEED_RANGE_MAX):
        prob_output = SEED_RANGE_MAX - 1
        # print("Comparison Table -- ECN Marking for Random Number {} < Output Value {}".format(random_number, prob_output))
        bfrt.sender.pipe.SwitchEgress.dcqcn_compare_probability.add_with_dcqcn_check_ecn_marking(dcqcn_prob_output=prob_output, dcqcn_random_number=random_number)



def log_tx_buffer_usage(timestamp, fout_tx_buffer, usage, watermark, drop_count):
    fout_tx_buffer.write("{}\t{}\t{}\t{}\n".format(timestamp, usage, watermark, drop_count))

def poll_tx_buffer_usage(expt_name):
    outfile = TX_BUFFER_DATA_DUMP_PATH + "/{}_tx_buff.dat".format(expt_name)
    fout = open(outfile, "w")
    while not stop_polling_tx_buffer.is_set():
        tx_buffer_stats = bfrt.tf1.tm.counter.queue.get(pg_id=get_pg_id(RECIRC_LPBK_PORT), pg_queue=0, pipe=0, print_ents=0).data
        timestamp = time.time()
        usage = tx_buffer_stats[b'usage_cells']
        watermark = tx_buffer_stats[b'watermark_cells']
        drop_count = tx_buffer_stats[b'drop_count_packets']
        log_tx_buffer_usage(timestamp, fout, usage, watermark, drop_count)
        time.sleep(0.010)
    fout.close()


def exec_remote_bfrt_command(switch, cmd):
    bash_cmd_string = "ssh {} \"tmux send-keys -t bfrt.0 '{}' ENTER\"".format(switch, cmd)
    # print(bash_cmd_string)
    os.system(bash_cmd_string)

def start_tx_buff_polling(expt_name):
    global tx_buff_polling_thread
    stop_polling_tx_buffer.clear()
    tx_buff_polling_thread = threading.Thread(target=poll_tx_buffer_usage, args=[expt_name])
    tx_buff_polling_thread.start()

def stop_tx_buff_polling():
    stop_polling_tx_buffer.set()
    tx_buff_polling_thread.join()

def start_rx_counters_polling(expt_name, poll_rx_buff):
    cmd = "ssh {} \"env SDE_INSTALL={} {} {} {} 0\" 2>&1 > /dev/null &".format(ssh_alias_rx_switch, sde_install_on_rx, poll_rx_counters_script_on_rx, expt_name, poll_rx_buff)
    os.system(cmd)

def start_rx_counters_polling_ext(expt_name):
    # os.system("ssh tofino1b \"env SDE_INSTALL=/home/cirlab/bf-sde-9.9.0/install /home/cirlab/jarvis-tofino/linkradar/expt_scripts/effective_lossRate_linkSpeed/poll_rx_counters.py {} {} 0\" 2>&1 > /dev/null &".format(expt_name, 0)) # we don't poll buffer counters
    os.system("ssh {} \"env SDE_INSTALL=/home/cirlab/bf-sde-9.11.1/install /home/cirlab/jarvis-tofino/linkradar/expt_scripts/effective_lossRate_linkSpeed/poll_rx_counters.py {} {} 0\" 2>&1 > /dev/null &".format(ssh_alias_topo_switch, expt_name, 0)) # we don't poll buffer counters

def stop_rx_counters_polling():
    os.system("ssh {} \"pkill -2 -f poll_rx\"".format(ssh_alias_rx_switch))

def stop_rx_counters_polling_ext():
    # os.system("ssh tofino1b \"pkill -2 -f poll_rx\"")
    os.system("ssh {} \"pkill -2 -f poll_rx\"".format(ssh_alias_topo_switch))


def run_effective_lossRate_linkSpeed_expt(expt_name, poll_buffs, num_pkts, nb_mode=False, rand_drop=False):

    if poll_buffs not in [0,1]:
        print("poll_buffs param should be 0 or 1")
        return

    logfile = TX_BUFFER_DATA_DUMP_PATH + "/{}_expt.log".format(expt_name)
    fout_log = open(logfile, "w")

    stop_traffic() # if any
    unlimit_trafficgen()
    reset_trafficgen_counter()

    try:
        disable_protection(32)
    except:
        pass

    if nb_mode:
        enable_protection(32, 0)  # non-blocking mode
    else:
        enable_protection(32, 1) # blocking mode
    

    # Step 0: Clear port and other counters on both sides
    # bfrt.port.port_stat.clear()
    # reg_buffered_pkts_eg_stats.clear() # to clear sent for buffering pkts
    print("Resetting counters on all switches... ", end="", flush=True)
    reset_all()
    # input("reset_all() on RX switch and topo switch and press enter...")
    exec_remote_bfrt_command(ssh_alias_rx_switch, "reset_all()")
    exec_remote_bfrt_command(ssh_alias_topo_switch, "reset_all()")
    time.sleep(5)
    print("Done")


    # Step 1: start traffic
    start_traffic()
    print("Traffic started")

    # poll_buffs param
    if poll_buffs:
        poll_buffs_param = 1
    else:
        poll_buffs_param = 0

    # Step 2a: start polling on tofino1b/p4campus-proc1 or tofino1c 
    if nb_mode:
        start_rx_counters_polling_ext(expt_name)        
    else:
        start_rx_counters_polling(expt_name, poll_buffs_param)
    print("Rx counter polling started")

    # Step 2b: start polling on self for tx buffer
    if poll_buffs == 1:
        start_tx_buff_polling(expt_name)
        print("Tx counter polling started")

    # Step 3: keep checking if target number of pkts are sent
    pkts_sent = 0
    while pkts_sent < num_pkts:
        try:
            pkts_sent = get_sent_for_tx_buffering()  # RJ: revert back
            print("{} ".format(pkts_sent), end="", flush=True)
            time.sleep(1)
        except KeyboardInterrupt:
            break

    print("") # for new line
    # Step 4a: stop polling on self for tx buffer
    if poll_buffs == 1:
        stop_tx_buff_polling()
        print("Tx counter polling stopped")

    # Step 4b: stop polling on tofino1b or tofino1c
    if nb_mode:
        stop_rx_counters_polling_ext()
    else: 
        stop_rx_counters_polling()
    print("Rx counter polling stopped")

    # Step 5: stop the traffic
    stop_traffic()
    print("Traffic stopped")

    print("Getting final counters")
    time.sleep(2)
    # Step 6a: get counters and compute VOA loss rate
    rx_ok = get_rx_ok_counter(rand_drop)
    tx_all = get_tx_all()
    print("tx all:", tx_all)
    fout_log.write("tx all:{}\n".format(tx_all))
    print("rx ok:", rx_ok)
    fout_log.write("rx ok:{}\n".format(rx_ok))

    # bfrt.port.port_stat.get(DEV_PORT=32, print_ents=0).data[b'$FramesTransmittedAll']
    voa_flr = (tx_all - rx_ok)/tx_all

    # Step 6b: get counters and compute effective loss rate
    data_pkts_sent_to_rx = get_sent_for_tx_buffering()
    data_pkts_forwarded_by_rx = get_rx_forwarded_counter(nb_mode)
    print("data pkts sent:", data_pkts_sent_to_rx)
    fout_log.write("data pkts sent:{}\n".format(data_pkts_sent_to_rx))
    print("data pkts forwarded ahead:", data_pkts_forwarded_by_rx)
    fout_log.write("data pkts forwarded ahead:{}\n".format(data_pkts_forwarded_by_rx))

    effective_flr = (data_pkts_sent_to_rx - data_pkts_forwarded_by_rx)/data_pkts_sent_to_rx

    limit_trafficgen()
    reset_trafficgen_counter()

    print("\nVOA FLR: {:e}".format(voa_flr))
    fout_log.write("\nVOA FLR: {}\n".format(voa_flr))
    print("\nEffective FLR: {:e}".format(effective_flr))
    fout_log.write("\nEffective FLR: {}\n".format(effective_flr))
    print("{}\t{}".format(voa_flr, effective_flr))
    fout_log.write("\n{}\t{}\n".format(voa_flr, effective_flr))

    fout_log.close()

    curl_cmd = '''curl -X POST -H 'Content-Type: application/json' -d '{"value1":"Effective Loss Rate"}' https://maker.ifttt.com/trigger/Script_Expt_completed/with/key/gB88SULNID5Te0obIzRqK-6a-6EO6tHSSBT5ulPEBbT'''
    os.system(curl_cmd)


def copy_sw_data_effective_lossRate_linkSpeed_expt(expt_name, nb_mode, server_ssh_alias, dst_path):
    tx_file_list = []
    rx_file_list = []

    # prepare tx (self) file list 
    tx_log_file = expt_name + '_expt.log'
    tx_buff_file = expt_name + '_tx_buff.dat'
    tx_file_list.append(TX_BUFFER_DATA_DUMP_PATH + '/' + tx_log_file)
    tx_file_list.append(TX_BUFFER_DATA_DUMP_PATH + '/' + tx_buff_file)
    # print(tx_file_list)

    # prepare rx switch file list
    rx_byte_counts_file = expt_name + '_forwarded_byte_counts.dat'
    rx_buff_file = expt_name + '_rx_buff.dat'
    rx_file_list.append(TX_BUFFER_DATA_DUMP_PATH + '/' + rx_byte_counts_file)
    if nb_mode == False: # we will have Rx buffer only for blocking mode
        rx_file_list.append(TX_BUFFER_DATA_DUMP_PATH + '/' + rx_buff_file)
    # print(rx_file_list)

    # copy tx (self) files
    print("Copying files from Tx switch... ", end="", flush=True)
    cmd_tx = "scp {} {}:{}".format(" ".join(tx_file_list), server_ssh_alias, dst_path)
    # print(cmd_tx)
    os.system(cmd_tx)
    print("Done")

    # copy rx files
    print("Copying files from Rx switch... ", end="", flush=True)
    if nb_mode == False:
        rx_switch = ssh_alias_rx_switch
    else:
        rx_switch = ssh_alias_topo_switch
    cmd_rx = "ssh {} \"scp {} {}:{}\"".format(rx_switch, " ".join(rx_file_list), server_ssh_alias, dst_path)
    # print(cmd_rx)
    os.system(cmd_rx)
    print("Done")

# def poll_tx_buffer_usage(expt_name):
#     DATA_DUMP_PATH = '/home/cirlab/jarvis-tofino/linkradar/expt-data/apnet/buffer_usage'
#     buffer_readings = []
#     for i in range(1000000):
#         buffer_reading = bfrt.tf1.tm.counter.queue.get(pg_id=17, pg_queue=0, pipe=0, print_ents=0).data[b'usage_cells']
#         buffer_readings.append(buffer_reading)

#     print("Collected the buffer readings. Dumping to file now...", flush=True)
#     file_path = DATA_DUMP_PATH + "/" + str(expt_name) + ".dat"

# emulate_fixed_random_losses()

################################
## DEBUGGING FAILED RETX
################################
# On Rx: check_pkt_records(0,65535)
# Get below manually by running check_retx.py in dev_test dir
# failed_retx = [14054,27392,32704,41943,46201,59120]
# get_lack_hole_records()
# get_buffered_dropped_records()

# for s in failed_retx:
#     index = lack_hole_records.index((s+1, s))
#     start = index - 2
#     end = index + 2
#     print("{}:\n{}".format(s, lack_hole_records[start:end+1]))
#     for bd_record in buffered_dropped_records:
#         if bd_record[1] == s:
#             print(bd_record)  # lack while dropping the pkt
#     print("\n")
    



# era_correction.dump(table=True, from_hw=True)
# decide_retx_or_drop.dump(table=True, from_hw=True)
# retx_mcast_buffered_pkt.dump(table=True, from_hw=True)
# reg_holes.get(REGISTER_INDEX=65535, from_hw=True)

### [Tofino1a] Sender's problematic state before injected buffered pkt
# reg_seq_no.mod(REGISTER_INDEX=32, f1=1)
# reg_era.mod(REGISTER_INDEX=32, f1=255)
# reg_leading_ack_era.mod(REGISTER_INDEX=32, f1=1)
# Pkt Injection: send_buffered_pkt(32, 65535, 0) 

### [Tofino1c] Sender's problematic state before injected buffered pkt
## Manual change #1: manually add ports 1/- (40G) and 23/- (100G) to Tofino1c
## Manual change #2: in setup.py tx_dev_ports_to_protect = [52]
## IMP: use this to check sender state: check_sender_state(52) 
# reg_seq_no.mod(REGISTER_INDEX=52, f1=1)
# reg_era.mod(REGISTER_INDEX=52, f1=255)
# reg_leading_ack_era.mod(REGISTER_INDEX=52, f1=1)
# Pkt Injection: send_buffered_pkt(52, 65535, 0, "ens3f0")
