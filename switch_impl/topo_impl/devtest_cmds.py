import math
import time 

LOSS_RATE_TX_PORT = 172
LOSS_RATE_RX_PORT = 164
NUMBER_1BILLION = 1000000000
NUMBER_100MILLION = 100000000
CHECK_LOSS_RATE_MAX_PKTS = NUMBER_100MILLION

reg_emulated_drop_type = bfrt.topo.pipe.SwitchIngress.reg_emulated_drop_type
emulate_tcp_data_pkt_drop = bfrt.topo.pipe.SwitchIngress.emulate_tcp_data_pkt_drop
reg_tcp_data_pkt_cntr = bfrt.topo.pipe.SwitchIngress.reg_tcp_data_pkt_cntr
emulate_random_pkt_drop = bfrt.topo.pipe.SwitchIngress.emulate_random_pkt_drop

# emulate_pkt_drop_stats = bfrt.topo.pipe.SwitchIngress.emulate_pkt_drop_stats
if_tcp_data_pkt_stats = bfrt.topo.pipe.SwitchIngress.check_if_tcp_data_pkt_stats

reg_ecn_marking_threshold = bfrt.topo.pipe.SwitchEgress.reg_ecn_marking_threshold

dedup_drop_counter = bfrt.topo.pipe.SwitchIngress.dedup_drop_counter

EMULATED_DROP_TYPE_SELECTIVE = 1
EMULATED_DROP_TYPE_RANDOM = 2
RANDOM_GEN_BIT_WIDTH = 20

def check_status():
    
    drop_type = reg_emulated_drop_type.get(REGISTER_INDEX=0, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_emulated_drop_type.f1'][1]

    # ECN marking threshold
    cells = reg_ecn_marking_threshold.get(REGISTER_INDEX=0, from_hw=True, print_ents=False).data[b'SwitchEgress.reg_ecn_marking_threshold.f1'][1]

    threshold_kb = (cells * 80) / 1000

    print("ECN Marking Threshold (KB): ",threshold_kb)

    if(drop_type == 0):
        print("No drops configured!")
        return

    if drop_type == EMULATED_DROP_TYPE_SELECTIVE:
        tcp_data_pkt_drop = emulate_tcp_data_pkt_drop.get(handle=2, print_ents=False).key[b'meta.tcp_data_pkt_count']
        curr_tcp_data_pkt_count = reg_tcp_data_pkt_cntr.get(REGISTER_INDEX=0, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_tcp_data_pkt_cntr.f1'][1]
        print("Type: Selective")
        print("TCP Data Pkt to Drop: {}".format(tcp_data_pkt_drop))
        print("Current TCP Data Pkt Count: {}".format(curr_tcp_data_pkt_count))
        
    elif drop_type == EMULATED_DROP_TYPE_RANDOM:
        num_uniform_drops = emulate_random_pkt_drop.info(return_info=True, print_info=False)['usage']
        rand_range = pow(2,RANDOM_GEN_BIT_WIDTH)
        loss_rate = num_uniform_drops / rand_range
        print("Type: Random")
        print("Loss Rate: {:e}".format(loss_rate))
    
def drop_selective_pkt(pkt_number):
    """
    Sets a single pkt drop for TCP data pkt

    Parameters:
        pkt_number (uint16): The TCP data pkt to be dropped

    Returns:
        None
    """
    # check if drop already configured
    drop_type = reg_emulated_drop_type.get(REGISTER_INDEX=0, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_emulated_drop_type.f1'][1]
    if drop_type != 0:
        print("WARN: Dropping is already configured!")
        check_status()
        print("\nPlease call disable_pkt_dropping() first!")
        return

    reg_emulated_drop_type.mod(REGISTER_INDEX=0, f1=EMULATED_DROP_TYPE_SELECTIVE)
    emulate_tcp_data_pkt_drop.add_with_do_emulate_pkt_drop(tcp_data_pkt_count=pkt_number)

def drop_random_pkts(loss_rate):
    """
    Sets random pkt loss for given loss rate

    Parameters:
        loss_rate (float): The loss rate expressed as fraction. Example: 0.01 for 1%

    Returns:
        None
    """
    # check if drop already configured
    drop_type = reg_emulated_drop_type.get(REGISTER_INDEX=0, from_hw=True, print_ents=False).data[b'SwitchIngress.reg_emulated_drop_type.f1'][1]
    if drop_type != 0:
        print("WARN: Dropping is already configured!")
        check_status()
        print("\nPlease call disable_pkt_dropping() first!")
        return

    reg_emulated_drop_type.mod(REGISTER_INDEX=0, f1=EMULATED_DROP_TYPE_RANDOM)

    range_start = 0
    range_end = pow(2, RANDOM_GEN_BIT_WIDTH) - 1

    num_uniform_drops = math.floor(loss_rate * pow(2,RANDOM_GEN_BIT_WIDTH))
    uniform_drop_interval = range_end / (num_uniform_drops + 1)
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
    reg_emulated_drop_type.clear()
    reg_tcp_data_pkt_cntr.clear()
    emulate_tcp_data_pkt_drop.clear()
    emulate_random_pkt_drop.clear()

def reset_tcp_data_pkt_cntr():
    """
    Resets the tcp_data_pkt_cntr
    """
    reg_tcp_data_pkt_cntr.clear()


def get_table_counters():
    
    nop_count = if_tcp_data_pkt_stats.get(COUNTER_INDEX=0, from_hw=True, print_ents=False).data[b'$COUNTER_SPEC_PKTS']
    actual_action_count = if_tcp_data_pkt_stats.get(COUNTER_INDEX=1, from_hw=True, print_ents=False).data[b'$COUNTER_SPEC_PKTS']
    print("check_if_tcp_data_pkt:")
    print("\tnop: ",nop_count)
    print("\tactual_action: ", actual_action_count)

    # nop_count = emulate_pkt_drop_stats.get(COUNTER_INDEX=0, from_hw=True, print_ents=False).data[b'$COUNTER_SPEC_PKTS']
    # actual_action_count = emulate_pkt_drop_stats.get(COUNTER_INDEX=1, from_hw=True, print_ents=False).data[b'$COUNTER_SPEC_PKTS']
    # print("emulate_tcp_data_pkt_drop:")
    # print("\tnop: ",nop_count)
    # print("\tactual_action: ", actual_action_count)


# def clear_all_counters():
#     if_tcp_data_pkt_stats.clear()
#     # emulate_pkt_drop_stats.clear()
#     bfrt.port.port_stat.clear()

# 100KB for 10Gbps. Src: https://www.kernel.org/doc/html/latest/networking/dctcp.html
def ecn_marking_threshold(threshold_kb): 
    cells = math.ceil((threshold_kb * 1000)/80)
    reg_ecn_marking_threshold.mod(REGISTER_INDEX=0, f1=cells)

def remove_ecn_marking_threshold():
    reg_ecn_marking_threshold.clear()


def start_traffic():
    bfrt.tf1.pktgen.app_cfg.mod_with_trigger_timer_periodic(app_id=1, app_enable=True)


def stop_traffic():
    bfrt.tf1.pktgen.app_cfg.mod_with_trigger_timer_periodic(app_id=1, app_enable=False)


def get_tx_all():
    return bfrt.port.port_stat.get(DEV_PORT=LOSS_RATE_TX_PORT, print_ents=0).data[b'$FramesTransmittedAll']

def get_rx_ok():
    return bfrt.port.port_stat.get(DEV_PORT=LOSS_RATE_RX_PORT, print_ents=0).data[b'$FramesReceivedOK']


def test_loss_rate(max_pkt_count = NUMBER_100MILLION):
    stop_traffic() # if any
    
    # Clear port counters
    bfrt.port.port_stat.clear()
    
    start_traffic()

    pkts_sent = 0
    while pkts_sent < max_pkt_count:
        try:
            pkts_sent = get_tx_all()
            print("{} ".format(pkts_sent), end="", flush=True)
            time.sleep(1)
        except KeyboardInterrupt:
            break

    stop_traffic()

    time.sleep(1)

    rx_ok = get_rx_ok()
    tx_all = get_tx_all()

    flr = (tx_all - rx_ok)/tx_all


    print("\nFLR: {:e}".format(flr))

def check_dedup_drop_count():
    count = dedup_drop_counter.get(COUNTER_INDEX=0, from_hw=1, print_ents=0).data[b'$COUNTER_SPEC_PKTS']
    print("Dedup drop count:", count)

def reset_dedup_drop_count():
    dedup_drop_counter.clear()

def reset_all():
    if_tcp_data_pkt_stats.clear()
    bfrt.port.port_stat.clear()
    reset_dedup_drop_count()
