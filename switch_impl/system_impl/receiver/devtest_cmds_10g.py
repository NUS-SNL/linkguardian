
import math
import os
import time
import threading
from tabulate import tabulate

INTERNAL_RECIRC_PORT_PIPE_0 = 68
RECIRC_PORT_LACK_QID = 1
RECIRC_PORT_PIPE_0 = 20

DEVTEST_DIR = "/home/cirlab/jarvis-tofino/linkradar/system_impl/devtest"
RANDOM_GEN_BIT_WIDTH = 20


enable_protection_script = "/home/cirlab/jarvis-tofino/linkradar/system_impl/receiver/enable_protection_on_tx.py"
patronus_iperf3_script = "/home/raj/jarvis-tofino/linkradar/expt_scripts/throughput_expt/run_throughput_expt.sh"
rx_counters_poll_grpc_script="/home/cirlab/jarvis-tofino/linkradar/expt_scripts/effective_lossRate_linkSpeed/poll_rx_counters.py"

devports_to_check = {20:"rx_recirc_buff", 
                     28: "iperf_receiver_knowhere",
                     36:"protected_link_rx",
                     44:"rx_filtering_port", 
                     52: "large_topo_tofino1b_conn", 
                     60: "iperf_receiver_hajime"
                    }


RX_POLL_DATA_DUMP_PATH = '/home/cirlab/traces/congestion_signal_expts'
FORWARDING_PORT_TO_POLL = 28

stop_polling_rx_buffer = threading.Event()
rx_buff_polling_thread = None
stop_polling_rx_forward_bytes = threading.Event()
rx_forward_bytes_polling_thread = None


reg_expected_seq_no = bfrt.receiver_10g.pipe.SwitchIngress.reg_expected_seq_no
reg_ig_debug_counter = bfrt.receiver_10g.pipe.SwitchIngress.reg_debug_counter
reg_eg_debug_counter = bfrt.receiver_10g.pipe.SwitchEgress.reg_debug_counter
reg_leading_ack = bfrt.receiver_10g.pipe.SwitchEgress.reg_leading_ack
reg_leading_ack_era = bfrt.receiver_10g.pipe.SwitchEgress.reg_leading_ack_era
reg_leading_ack_notify_count = bfrt.receiver_10g.pipe.SwitchEgress.reg_leading_ack_notify_count
reg_ack = bfrt.receiver_10g.pipe.SwitchIngress.reg_ack
reg_ack_era = bfrt.receiver_10g.pipe.SwitchIngress.reg_ack_era
era_correction = bfrt.receiver_10g.pipe.SwitchIngress.era_correction
ig_debug_counter = bfrt.receiver_10g.pipe.SwitchIngress.ig_debug_counter
emulate_random_pkt_drop = bfrt.receiver_10g.pipe.SwitchIngress.emulate_random_pkt_drop
cntr_ig_debug = bfrt.receiver_10g.pipe.SwitchIngress.ig_debug_counter
cntr_ig_debug2 = bfrt.receiver_10g.pipe.SwitchIngress.ig_debug_counter2
reg_hole_sizes = bfrt.receiver_10g.pipe.SwitchIngress.reg_hole_sizes
cntr_eg_debug = bfrt.receiver_10g.pipe.SwitchEgress.eg_debug_counter
reg_recirc_buffer_pfc_pause_threshold = bfrt.receiver_10g.pipe.SwitchEgress.reg_recirc_buffer_pfc_pause_threshold
reg_recirc_buffer_pfc_resume_threshold = bfrt.receiver_10g.pipe.SwitchEgress.reg_recirc_buffer_pfc_resume_threshold
reg_pfc_curr_state = bfrt.receiver_10g.pipe.SwitchEgress.reg_pfc_curr_state
reg_pfc_gen_req = bfrt.receiver_10g.pipe.SwitchEgress.reg_pfc_gen_req
tbl_add_lack_hdr_or_drop_mirror_courier_pkt = bfrt.receiver_10g.pipe.SwitchEgress.add_lack_hdr_or_drop_mirror_courier_pkt
tbl_add_pfc_c1_quanta = bfrt.receiver_10g.pipe.SwitchEgress.add_pfc_c1_quanta # loss noti pfc
try:
    reg_lost_timestamps = bfrt.receiver_10g.pipe.SwitchIngress.reg_lost_timestamps
except:
    pass

reg_pause_ts_idx = bfrt.receiver_10g.pipe.SwitchEgress.reg_pause_ts_idx
reg_resume_ts_idx = bfrt.receiver_10g.pipe.SwitchEgress.reg_resume_ts_idx
reg_pause_ts = bfrt.receiver_10g.pipe.SwitchEgress.reg_pause_ts
reg_resume_ts = bfrt.receiver_10g.pipe.SwitchEgress.reg_resume_ts
reg_qdepth_record_idx = bfrt.receiver_10g.pipe.SwitchEgress.reg_qdepth_record_idx
reg_qdepth_records = bfrt.receiver_10g.pipe.SwitchEgress.reg_qdepth_records




# reg_ecn_marking_threshold = bfrt.receiver_10g.pipe.SwitchEgress.reg_ecn_marking_threshold


# reg_pkt_records = bfrt.receiver_10g.pipe.SwitchIngress.reg_pkt_records
# reg_pkt_record_idx = bfrt.receiver_10g.pipe.SwitchIngress.reg_pkt_record_idx

def get_pg_id(dev_port):
    # each pipe has 128 dev_ports + divide by 4 to get the pg_id
    pg_id = (dev_port % 128) >> 2 
    return pg_id

def get_pg_queue(dev_port, qid):
    lane = dev_port % 4
    pg_queue = lane * 8 + qid # there are 8 queues per lane
    return pg_queue


def check_receiver_state():
    expected_seq_no = reg_expected_seq_no.get(REGISTER_INDEX=36, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_expected_seq_no.f1'][0]
    leading_ack = reg_leading_ack.get(REGISTER_INDEX=36, from_hw=True, print_ents=False).data[b'SwitchEgress.reg_leading_ack.f1'][0]
    leading_ack_era = reg_leading_ack_era.get(REGISTER_INDEX=36, from_hw=True, print_ents=False).data[b'SwitchEgress.reg_leading_ack_era.f1'][0]
    leading_ack_notify_count = reg_leading_ack_notify_count.get(REGISTER_INDEX=36, from_hw=True, print_ents=False).data[b'SwitchEgress.reg_leading_ack_notify_count.f1'][0]
    eg_debug_counter = reg_eg_debug_counter.get(REGISTER_INDEX=0, from_hw=True, print_ents=False).data[b'SwitchEgress.reg_debug_counter.f1'][0]
    ig_debug_counter = reg_ig_debug_counter.get(REGISTER_INDEX=0, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_debug_counter.f1'][0]
    # ack = reg_ack.get(REGISTER_INDEX=36, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_ack.f1'][0]
    ack = reg_ack.get(REGISTER_INDEX=36, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_ack.ack_no'][0]
    ack_time_remaining = reg_ack.get(REGISTER_INDEX=36, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_ack.time_remaining'][0]
    ack_era = reg_ack_era.get(REGISTER_INDEX=36, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_ack_era.f1'][0]
    entries = emulate_random_pkt_drop.info(print_info=0, return_info=1)['usage']
    rand_range = pow(2, RANDOM_GEN_BIT_WIDTH)
    loss_rate = entries / rand_range
    ack_timeout_no_trigger_cntr = cntr_ig_debug.get(COUNTER_INDEX=1, from_hw=True, print_ents=False).data[b'$COUNTER_SPEC_PKTS']
    ack_timeout_trigger_cntr = cntr_ig_debug.get(COUNTER_INDEX=2, from_hw=True, print_ents=False).data[b'$COUNTER_SPEC_PKTS']
    # cells = reg_ecn_marking_threshold.get(REGISTER_INDEX=0, from_hw=True, print_ents=False).data[b'SwitchEgress.reg_ecn_marking_threshold.f1'][1]
    # ecn_threshold_kb = (cells * 80) / 1000

    resume_threshold = reg_recirc_buffer_pfc_resume_threshold.get(REGISTER_INDEX=0, from_hw=1, print_ents=0).data[b'SwitchEgress.reg_recirc_buffer_pfc_resume_threshold.f1'][0]
    pause_threshold = reg_recirc_buffer_pfc_pause_threshold.get(REGISTER_INDEX=0, from_hw=1, print_ents=0).data[b'SwitchEgress.reg_recirc_buffer_pfc_pause_threshold.f1'][0]
    pfc_curr_state = reg_pfc_curr_state.get(REGISTER_INDEX=0, from_hw=1, print_ents=0).data[b'SwitchEgress.reg_pfc_curr_state.f1'][0]
    pause_frames_requested = cntr_eg_debug.get(COUNTER_INDEX=0, from_hw=1, print_ents=0).data[b'$COUNTER_SPEC_PKTS']
    resume_frames_requested = cntr_eg_debug.get(COUNTER_INDEX=1, from_hw=1, print_ents=0).data[b'$COUNTER_SPEC_PKTS']
    pfc_gen_frames_dropped = cntr_eg_debug.get(COUNTER_INDEX=3, from_hw=1, print_ents=0).data[b'$COUNTER_SPEC_PKTS']
    pause_frames_sent = cntr_eg_debug.get(COUNTER_INDEX=4, from_hw=1, print_ents=0).data[b'$COUNTER_SPEC_PKTS']
    resume_frames_sent = cntr_eg_debug.get(COUNTER_INDEX=5, from_hw=1, print_ents=0).data[b'$COUNTER_SPEC_PKTS']

    # lack_updates_sent_for_mirroring = cntr_ig_debug2.get(COUNTER_INDEX=0, from_hw=True, print_ents=False).data[b'$COUNTER_SPEC_PKTS']
    # lack_updates_received_after_mirroring = cntr_eg_debug.get(COUNTER_INDEX=6, from_hw=True, print_ents=False).data[b'$COUNTER_SPEC_PKTS']

    pfc_loss_noti_entry = tbl_add_pfc_c1_quanta.get(egress_port=36, print_ents=0)

    if pfc_loss_noti_entry == -1:
        pfc_on_loss_noti_enabled = "False"
        pfc_loss_noti_quanta = "N/A"        
    else:
        pfc_on_loss_noti_enabled = "True"
        pfc_loss_noti_quanta = str(pfc_loss_noti_entry.data[b'c1_quanta'])
    
    print("expected_seq_no:", expected_seq_no)
    # print("ack:", ack)
    print("ack (time_remaining): {} ({})".format(ack, ack_time_remaining))
    print("ack_era:", ack_era)
    print("leading_ack:", leading_ack)
    print("leading_ack_era:", leading_ack_era)
    print("leading_ack_notify_count:", leading_ack_notify_count)
    print("ig_debug_counter:", ig_debug_counter)
    print("eg_debug_counter:", eg_debug_counter)
    print("timeout_pkt_no_trigger_cntr:", ack_timeout_no_trigger_cntr)
    print("timeout_pkt_trigger_cntr:", ack_timeout_trigger_cntr)
    print("LOSS RATE: {:e}".format(loss_rate))
    # print("\nECN Marking Threshold: {}KB ({} cells)".format(ecn_threshold_kb,
    # cells))
    # print("\n")
    print("PFC resume threshold: {} cells".format(resume_threshold))
    print("PFC pause threshold: {} cells".format(pause_threshold))
    # print("PFC curr state: {}".format(pfc_curr_state))
    # print("PFC PAUSE frames requested: {}".format(pause_frames_requested))
    # print("PFC RESUME frames requested: {}".format(resume_frames_requested))
    # print("PFC PAUSE frames sent: {}".format(pause_frames_sent))
    # print("PFC RESUME frames sent: {}".format(resume_frames_sent))
    # print("PFC gen frames dropped: {}".format(pfc_gen_frames_dropped))
    # print("PFC gen on loss noti enabled: {} ({} cells)".format(pfc_on_loss_noti_enabled, pfc_loss_noti_quanta))
    # print("\n")
    # print("lack_updates_sent_for_mirroring: {}".format(lack_updates_sent_for_mirroring))
    # print("lack_updates_received_after_mirroring: {}".format(lack_updates_received_after_mirroring))


def get_ig_debug_counter():
    debug_counter = reg_ig_debug_counter.get(REGISTER_INDEX=0, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_debug_counter.f1'][0]
    print(debug_counter)
 
def reset_all():
    bfrt.port.port_stat.clear()
    
    reg_expected_seq_no.clear()
    reg_eg_debug_counter.clear()
    reg_ig_debug_counter.clear()

    reg_leading_ack.clear()
    reg_leading_ack_era.clear()
    reg_leading_ack_notify_count.clear()

    reg_ack.clear()
    reg_ack_era.clear()

    cntr_ig_debug.clear() # currently timeout_pkt_cntr_no_trigger and trigger
    cntr_eg_debug.clear()

    reg_hole_sizes.clear()

    clear_buffer_peak_usage()
    clear_tm_egress_port_drops()
    
    # reg_pkt_records.clear()
    # reg_pkt_record_idx.clear()


# def check_pkt_records(start, end):
#     fout = open(DEVTEST_DIR + "/rx_pkt_log.dat", "w")
#     for idx in range(start, end+1):
#         seq_no = reg_pkt_records.get(REGISTER_INDEX=idx, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_pkt_records.seq_no'][0]
#         ts = reg_pkt_records.get(REGISTER_INDEX=idx, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_pkt_records.ts'][0]
#         fout.write("{}: {}\n".format(seq_no, ts))
#         # print("{}: {}".format(seq_no, ts))
    
#     fout.close()

def drop_random_pkts(loss_rate):
    """
    Sets random pkt loss for given loss rate

    Parameters:
        loss_rate (float): The loss rate expressed as fraction. Example: 0.01 for 1%

    Returns:
        None
    """
    # check if drop already configured
    entries = emulate_random_pkt_drop.info(print_info=0, return_info=1)['usage']
    rand_range = pow(2, RANDOM_GEN_BIT_WIDTH)
    curr_loss_rate = entries / rand_range

    if entries != 0:
        print("WARN: Dropping is already configured!")
        print("Loss Rate: {:e}".format(curr_loss_rate))
        print("\nPlease call disable_pkt_dropping() first!")
        return

    # reg_emulated_drop_type.mod(REGISTER_INDEX=0, f1=EMULATED_DROP_TYPE_RANDOM)

    range_start = 0
    range_end = pow(2, RANDOM_GEN_BIT_WIDTH) - 1
    print("range_end: ",range_end)
    num_uniform_drops = math.floor(loss_rate * pow(2,RANDOM_GEN_BIT_WIDTH))
    print("num_uniform_drops: ", num_uniform_drops)
    uniform_drop_interval = range_end / (num_uniform_drops + 1)
    print("uniform_drop_interval: ", uniform_drop_interval)
    uniform_drops = []

    curr_drop = range_start
    for i in range(num_uniform_drops):
        curr_drop += uniform_drop_interval
        uniform_drops.append(round(curr_drop))
    
    print("Adding {} entries to emulate_random_pkt_drop".format(len(uniform_drops), flush=True))
    bfrt.batch_begin()
    for pkt_drop in uniform_drops:
        emulate_random_pkt_drop.add_with_do_emulate_pkt_drop(curr_rand_number=pkt_drop)
    bfrt.batch_flush()
    bfrt.batch_end()
    


def disable_pkt_dropping():
    """
    Clears all configured pkt drops and their state
    """
    emulate_random_pkt_drop.clear()

def start_ack_timeout_traffic():
    bfrt.tf1.pktgen.app_cfg.mod_with_trigger_timer_periodic(app_id=1, app_enable=True)

def stop_ack_timeout_traffic():
    bfrt.tf1.pktgen.app_cfg.mod_with_trigger_timer_periodic(app_id=1, app_enable=False)

def clear_port_stats_counters():
    bfrt.port.port_stat.clear()

def get_buffer_peak_usage():
    internal_recirc_lack_updates_buffer_peak = bfrt.tf1.tm.counter.queue.get(pg_id=get_pg_id(INTERNAL_RECIRC_PORT_PIPE_0), pg_queue=get_pg_queue(INTERNAL_RECIRC_PORT_PIPE_0, RECIRC_PORT_LACK_QID), pipe=0, print_ents=0).data[b'watermark_cells']
    recirc_buffer_peak = bfrt.tf1.tm.counter.queue.get(pg_id=get_pg_id(RECIRC_PORT_PIPE_0), pg_queue=get_pg_queue(RECIRC_PORT_PIPE_0, 0), pipe=0, print_ents=0).data[b'watermark_cells']
    buffer_peak_protected_link_rx_normal = bfrt.tf1.tm.counter.queue.get(pg_id=get_pg_id(36), pg_queue=get_pg_queue(36, 0), pipe=0, print_ents=0).data[b'watermark_cells']
    buffer_peak_protected_link_rx_high = bfrt.tf1.tm.counter.queue.get(pg_id=get_pg_id(36), pg_queue=get_pg_queue(36, 2), pipe=0, print_ents=0).data[b'watermark_cells']
    buffer_peak_protected_link_rx_low = bfrt.tf1.tm.counter.queue.get(pg_id=get_pg_id(36), pg_queue=get_pg_queue(36, 1), pipe=0, print_ents=0).data[b'watermark_cells']
    filtering_buffer_peak = bfrt.tf1.tm.counter.queue.get(pg_id=get_pg_id(44), pg_queue=get_pg_queue(44, 0), pipe=0, print_ents=0).data[b'watermark_cells']
    buffer_peak_iperf_receiver_port_hajime = bfrt.tf1.tm.counter.queue.get(pg_id=get_pg_id(60), pg_queue=get_pg_queue(60, 0), pipe=0, print_ents=0).data[b'watermark_cells']
    buffer_peak_iperf_receiver_port_knowhere = bfrt.tf1.tm.counter.queue.get(pg_id=get_pg_id(28), pg_queue=get_pg_queue(28, 0), pipe=0, print_ents=0).data[b'watermark_cells']
    forwarding_ahead_port_buff_peak = bfrt.tf1.tm.counter.queue.get(pg_id=get_pg_id(52), pg_queue=get_pg_queue(52, 0), pipe=0, print_ents=0).data[b'watermark_cells']
    
    print("Rx buffering: {}".format(recirc_buffer_peak))
    print("Protected Link Rx (high): {}".format(buffer_peak_protected_link_rx_high))
    print("Protected Link Rx (normal): {}".format(buffer_peak_protected_link_rx_normal))
    print("Protected Link Rx (low): {}".format(buffer_peak_protected_link_rx_low))
    print("iperf receiver port (hajime): {}".format(buffer_peak_iperf_receiver_port_hajime))
    print("iperf receiver port (knowhere): {}".format(buffer_peak_iperf_receiver_port_knowhere))
    print("filtering port buffer peak: {}".format(filtering_buffer_peak))
    print("internal recirc port (68) lack update queue: {}".format(internal_recirc_lack_updates_buffer_peak))
    print("forwarding ahead port (52) buffer peak: {}".format(forwarding_ahead_port_buff_peak))
    return

def clear_buffer_peak_usage():
    bfrt.tf1.tm.counter.queue.clear()

def get_hole_size_stats():
    holes_1 = reg_hole_sizes.get(REGISTER_INDEX=1, from_hw=1, print_ents=0).data[b'SwitchIngress.reg_hole_sizes.f1'][0]
    holes_2 = reg_hole_sizes.get(REGISTER_INDEX=2, from_hw=1, print_ents=0).data[b'SwitchIngress.reg_hole_sizes.f1'][0]
    holes_3 = reg_hole_sizes.get(REGISTER_INDEX=3, from_hw=1, print_ents=0).data[b'SwitchIngress.reg_hole_sizes.f1'][0]
    holes_4 = reg_hole_sizes.get(REGISTER_INDEX=4, from_hw=1, print_ents=0).data[b'SwitchIngress.reg_hole_sizes.f1'][0]
    holes_5 = reg_hole_sizes.get(REGISTER_INDEX=5, from_hw=1, print_ents=0).data[b'SwitchIngress.reg_hole_sizes.f1'][0]
    holes_6 = reg_hole_sizes.get(REGISTER_INDEX=6, from_hw=1, print_ents=0).data[b'SwitchIngress.reg_hole_sizes.f1'][0]
    holes_7 = reg_hole_sizes.get(REGISTER_INDEX=7, from_hw=1, print_ents=0).data[b'SwitchIngress.reg_hole_sizes.f1'][0]
    holes_8 = reg_hole_sizes.get(REGISTER_INDEX=8, from_hw=1, print_ents=0).data[b'SwitchIngress.reg_hole_sizes.f1'][0]
    holes_9 = reg_hole_sizes.get(REGISTER_INDEX=9, from_hw=1, print_ents=0).data[b'SwitchIngress.reg_hole_sizes.f1'][0]

    pkts_retx_hole_1 = holes_1 + holes_2 + holes_3 + holes_4 + holes_5 \
        + holes_6 + holes_7 + holes_8 + holes_9
    pkts_retx_hole_2 = holes_2 + holes_3 + holes_4 + holes_5 \
        + holes_6 + holes_7 + holes_8 + holes_9
    pkts_retx_hole_3 = holes_3 + holes_4 + holes_5 \
        + holes_6 + holes_7 + holes_8 + holes_9
    pkts_retx_hole_4 = holes_4 + holes_5 \
        + holes_6 + holes_7 + holes_8 + holes_9
    pkts_retx_hole_5 = holes_5 \
        + holes_6 + holes_7 + holes_8 + holes_9

    print("holes_size_1: {}".format(holes_1))
    print("holes_size_2: {}".format(holes_2))
    print("holes_size_3: {}".format(holes_3))
    print("holes_size_4: {}".format(holes_4))
    print("holes_size_5: {}".format(holes_5))
    print("holes_size_6: {}".format(holes_6))
    print("holes_size_7: {}".format(holes_7))
    print("holes_size_8: {}".format(holes_8))
    print("holes_size_9: {}".format(holes_9))

    print("Expected reTx (hole_1): {}".format(pkts_retx_hole_1))
    print("Expected reTx (hole_2): {}".format(pkts_retx_hole_2))
    print("Expected reTx (hole_3): {}".format(pkts_retx_hole_3))
    print("Expected reTx (hole_4): {}".format(pkts_retx_hole_4))
    print("Expected reTx (hole_5): {}".format(pkts_retx_hole_5))


def get_mode_counters():
    nb_count = ig_debug_counter.get(COUNTER_INDEX=3, from_hw=1, print_ents=0).data[b'$COUNTER_SPEC_PKTS']
    b_count = ig_debug_counter.get(COUNTER_INDEX=0, from_hw=1, print_ents=0).data[b'$COUNTER_SPEC_PKTS']

    print("NB mode: {}".format(nb_count))
    print("B mode: {}".format(b_count))


# 100KB for 10Gbps and 30KB for 1Gbps
# Src: https://www.kernel.org/doc/html/latest/networking/dctcp.html
# def set_ecn_marking_threshold(threshold_kb=100): 
#     cells = math.ceil((threshold_kb * 1000)/80)
#     reg_ecn_marking_threshold.mod(REGISTER_INDEX=0, f1=cells)

# def remove_ecn_marking_threshold():
#     reg_ecn_marking_threshold.clear()


def set_recirc_buff_pfc_pause_threshold(threshold_bytes=14400): 
    cells = math.ceil(threshold_bytes/80)
    reg_recirc_buffer_pfc_pause_threshold.mod(REGISTER_INDEX=0, f1=cells)

def get_recirc_buff_pfc_pause_threshold():
    cells = reg_recirc_buffer_pfc_pause_threshold.get(REGISTER_INDEX=0, print_ents=False, from_hw=True).data[b'SwitchEgress.reg_recirc_buffer_pfc_pause_threshold.f1'][0]
    print("{} bytes ({} cells)".format(cells * 80, cells))

def remove_recirc_buff_pfc_pause_threshold():
    reg_recirc_buffer_pfc_pause_threshold.clear()

def set_recirc_buff_pfc_resume_threshold(threshold_bytes=11200): 
    cells = math.ceil(threshold_bytes/80)
    reg_recirc_buffer_pfc_resume_threshold.mod(REGISTER_INDEX=0, f1=cells)

def get_recirc_buff_pfc_resume_threshold():
    cells = reg_recirc_buffer_pfc_resume_threshold.get(REGISTER_INDEX=0, print_ents=False, from_hw=True).data[b'SwitchEgress.reg_recirc_buffer_pfc_resume_threshold.f1'][0]
    print("{} bytes ({} cells)".format(cells * 80, cells))

def remove_recirc_buff_pfc_resume_threshold():
    reg_recirc_buffer_pfc_resume_threshold.clear()


def get_tm_egress_port_drops():
    global devports_to_check
    
    tbl_tm_eg_counter = bfrt.tf1.tm.counter.eg_port

    tm_eg_port_drops = []

    for devport in devports_to_check:
        eg_drops = tbl_tm_eg_counter.get(dev_port=devport, print_ents=False, from_hw=True).data[b'drop_count_packets']
        tm_eg_port_drops.append([devport, devports_to_check[devport], eg_drops])
    
    print(tabulate(tm_eg_port_drops))


def clear_tm_egress_port_drops():
    tbl_tm_eg_counter = bfrt.tf1.tm.counter.eg_port
    tbl_tm_eg_counter.clear()

def set_loss_noti_pfc_quanta(quanta, eg_port=36):
    tbl_add_pfc_c1_quanta = bfrt.receiver_10g.pipe.SwitchEgress.add_pfc_c1_quanta
    try:
        tbl_add_pfc_c1_quanta.mod_with_do_add_pfc_c1_quanta(egress_port=eg_port, c1_quanta=quanta)
    except:
        tbl_add_pfc_c1_quanta.add_with_do_add_pfc_c1_quanta(egress_port=eg_port, c1_quanta=quanta)

def get_loss_noti_pfc_quanta(eg_port=36):
    tbl_add_pfc_c1_quanta = bfrt.receiver_10g.pipe.SwitchEgress.add_pfc_c1_quanta
    try:
        quanta = tbl_add_pfc_c1_quanta.get(egress_port=eg_port, print_ents=0).data[b'c1_quanta']
        print(quanta)
    except:
        print("No entry found for eg_port: {}".format(eg_port))

def get_recirc_buff_pfc_frame_count():
    requested_via_mirror_pause = cntr_eg_debug.get(COUNTER_INDEX=0, print_ents=0, from_hw=1).data[b'$COUNTER_SPEC_PKTS']
    requested_via_mirror_resume = cntr_eg_debug.get(COUNTER_INDEX=1, print_ents=0, from_hw=1).data[b'$COUNTER_SPEC_PKTS']
    actual_pfc_frames_sent = cntr_eg_debug.get(COUNTER_INDEX=2, print_ents=0, from_hw=1).data[b'$COUNTER_SPEC_PKTS'] 
    print("Requested via mirroring (PAUSE):", requested_via_mirror_pause)
    print("Requested via mirroring (RESUME):", requested_via_mirror_resume)
    print("TOTAL PFC frames sent:", actual_pfc_frames_sent)


def get_courier_pkt_send_out_rate():
    start_count = tbl_add_lack_hdr_or_drop_mirror_courier_pkt.get(is_lack_pending=1, valid=1, from_hw=1, print_ents=False).data[b'$COUNTER_SPEC_PKTS']
    time.sleep(10)
    end_count = tbl_add_lack_hdr_or_drop_mirror_courier_pkt.get(is_lack_pending=1, valid=1, from_hw=1, print_ents=False).data[b'$COUNTER_SPEC_PKTS']
    rate = (end_count-start_count)/10
    print(rate)

def start_tx_counters_polling(expt_name):
    os.system("ssh tofino1a \"env SDE_INSTALL=/home/cirlab/bf-sde-9.10.0/install /home/cirlab/jarvis-tofino/linkradar/expt_scripts/congestion_signal_expts/poll_tx_counters.py {}\" 2>&1 > /dev/null &".format(expt_name))

def stop_tx_counters_polling():
    os.system("ssh tofino1a \"pkill -2 -f poll_tx\"")

def log_rx_buffer_usage(fout_tx_buffer, usage, watermark, drop_count):
    fout_tx_buffer.write("{}\t{}\t{}\n".format(usage, watermark, drop_count))

def poll_rx_buffer_usage(expt_name):
    outfile = RX_POLL_DATA_DUMP_PATH + "/{}_rx_buff.dat".format(expt_name)
    fout = open(outfile, "w")
    while not stop_polling_rx_buffer.is_set():
        tx_buffer_stats = bfrt.tf1.tm.counter.queue.get(pg_id=get_pg_id(RECIRC_PORT_PIPE_0), pg_queue=0, pipe=0, print_ents=0).data
        usage = tx_buffer_stats[b'usage_cells']
        watermark = tx_buffer_stats[b'watermark_cells']
        drop_count = tx_buffer_stats[b'drop_count_packets']
        fout.write("{}\t{}\t{}\n".format(usage, watermark, drop_count))
        # log_rx_buffer_usage(fout, usage, watermark, drop_count)
        time.sleep(0.010)
    fout.close()

def start_rx_buff_polling(expt_name):
    global rx_buff_polling_thread
    stop_polling_rx_buffer.clear()
    rx_buff_polling_thread = threading.Thread(target=poll_rx_buffer_usage, args=[expt_name])
    rx_buff_polling_thread.start()

def stop_rx_buff_polling():
    stop_polling_rx_buffer.set()

def enable_protection_on_tx():
    os.system(enable_protection_script)

def start_endhost_tcp_traffic(expt_name):
    os.system("ssh patronus \"{} {} BBR 30\" &".format(patronus_iperf3_script, expt_name))

def start_endhost_rdma_traffic():
    input("Start RDMA traffic manually...")

def stop_endhost_tcp_traffic():
    print("Nothing to do for stopping TCP traffic")

def stop_endhost_rdma_traffic():
    input("Stop RDMA traffic manually...")

def start_endhost_traffic(expt_name, traffic_type):
    if traffic_type == 0:
        print("Starting TCP traffic...")
        start_endhost_tcp_traffic(expt_name)
    elif traffic_type == 1:
        print("Starting RDMA traffic...")
        start_endhost_rdma_traffic()

def stop_endhost_traffic(traffic_type):
    if traffic_type == 0:
        print("Stopping TCP traffic...")
        stop_endhost_tcp_traffic()
    elif traffic_type == 1:
        print("Stopping RDMA traffic...")
        stop_endhost_rdma_traffic()



def log_speed_byte_counts(fout_speed, timestamp, byte_counts):
    fout_speed.write("{}\t{}\n".format(timestamp, byte_counts))

def poll_forward_speed_byte_counts(expt_name):
    speed_outfile = RX_POLL_DATA_DUMP_PATH + "/{}_forwarded_byte_counts.dat".format(expt_name)
    fout_speed = open(speed_outfile, "w")
    while not stop_polling_rx_forward_bytes.is_set():
        byte_count = bfrt.port.port_stat.get(DEV_PORT=FORWARDING_PORT_TO_POLL, print_ents=False).data[b'$OctetsTransmittedTotal']
        log_speed_byte_counts(fout_speed, time.time(), byte_count)
        time.sleep(0.1)
    fout_speed.close()

def start_rx_forward_bytes_polling(expt_name):
    global rx_forward_bytes_polling_thread
    stop_polling_rx_forward_bytes.clear()
    rx_forward_bytes_polling_thread = threading.Thread(target=poll_forward_speed_byte_counts, args=[expt_name])
    rx_forward_bytes_polling_thread.start()

def stop_rx_forward_bytes_polling():
    stop_polling_rx_forward_bytes.set()

def start_rx_counters_polling(expt_name):
    os.system("{} {} 1 1 2>&1 > /dev/null &".format(rx_counters_poll_grpc_script, expt_name))

def stop_rx_counters_polling():
    os.system("pkill -2 -f poll_rx")

def run_congestion_signal_expt(expt_name, traffic_type):

    if traffic_type not in [0,1]:
        print("traffic_type: 0 for tcp and 1 for rdma")
        return

    disable_pkt_dropping()
    reset_all()

    input("(1) Reset sender. (2) Disable protection on sender. Then press enter...")
    input("Start rx counters polling manually... and press enter")

    print("Start time: {}".format(time.time()))
    # Step 1: start traffic
    print("Starting endhost traffic...")
    start_endhost_traffic(expt_name, traffic_type)
    time.sleep(5)

    # Step 2: start polling counters
    print("Starting Tx counters polling")
    # start_rx_buff_polling(expt_name)
    # start_rx_forward_bytes_polling(expt_name)
    # start_rx_counters_polling(expt_name)
    start_tx_counters_polling(expt_name)

    print("Sleeping for 5 seconds", flush=True)
    time.sleep(5)

    # Step 3: start corruption 
    print("Starting random pkt drop", flush=True)
    drop_random_pkts(0.001)

    print("Sleeping for 5 seconds", flush=True)
    time.sleep(5)

    # Step 4: enable blocking mode protection
    print("Enabling protection on the sender (auto done by tx poll)")
    # enable_protection_on_tx()

    print("Sleeping for 7 seconds", flush=True)
    time.sleep(7)

    # Step 5: stop polling counters
    print("Stopping tx counters polling")
    # stop_rx_buff_polling()
    # stop_rx_forward_bytes_polling()
    stop_tx_counters_polling()

    # Step 6: stop the traffic
    print("Stopping endhost traffic")
    stop_endhost_traffic(traffic_type)
    print("End time: {}".format(time.time()))

    input("Stop rx counters polling manually... and press enter")

