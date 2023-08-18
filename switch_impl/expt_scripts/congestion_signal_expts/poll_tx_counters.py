#!/usr/bin/env python3

from glob import glob
import os
import sys
import time
import threading
import signal


END_POINT_SENDER_PORT = 60
TX_PROTECTED_PORT = 32

OUTPATH = "/home/cirlab/traces/congestion_signal_expts"

stop_polling_tx_buffer = threading.Event()
tx_buffer_poll_thread = None
stop_polling_send_rate_byte_counts = False
fout_send_rate = None
fout_buffer = None
send_rate_outfile = None
buff_outfile = None
link_protect_table = None
link_protect_key = None
link_protect_data = None


if len(sys.argv) != 2:
    print("Usage: {} <expt_name>".format(sys.argv[0]))    
    sys.exit(1)


def cleanup():
    global stop_polling_send_rate_byte_counts
    print("Stopping rx buffer poll thread...")
    stop_polling_tx_buffer.set()
    print("Stopping speed byte counts polling...")
    stop_polling_send_rate_byte_counts = True
    tx_buffer_poll_thread.join()

def signal_handler(sig, frame):
    print('Caught Ctrl+C!')
    print("Stopping and cleaning up...")
    cleanup()

signal.signal(signal.SIGINT, signal_handler)


expt_name = sys.argv[1]


stop_polling_tx_buffer.clear()

send_rate_outfile = OUTPATH + "/{}_sendrate_byte_counts.dat".format(expt_name)
buff_outfile = OUTPATH + "/{}_tx_link_buff.dat".format(expt_name)

fout_send_rate = open(send_rate_outfile, "w")
fout_buffer = None


fout_buffer = open(buff_outfile, "w")

SDE_INSTALL = os.environ['SDE_INSTALL']
PYTHON3_VER = '{}.{}'.format(
    sys.version_info.major,
    sys.version_info.minor)
SDE_PYTHON3 = os.path.join(SDE_INSTALL, 'lib', 'python' + PYTHON3_VER,
                             'site-packages')
sys.path.append(SDE_PYTHON3)
sys.path.append(os.path.join(SDE_PYTHON3, 'tofino'))
sys.path.append(os.path.join(SDE_PYTHON3, 'tofino', 'bfrt_grpc'))

import bfrt_grpc.client as gc


BFRT_CLIENT_ID = 99

bfrt_endpoint = 'localhost'
bfrt_port = 50052
bfrt_info = None
dev_tgt = None
dev_tgt_pipe0 = None
interface = None
port_stat_table = None
byte_count_key = None
queue_usage_key = None
queue_counters_table = None



def get_pg_id(dev_port):
    # each pipe has 128 dev_ports + divide by 4 to get the pg_id
    pg_id = (dev_port % 128) >> 2 
    return pg_id

def get_pg_queue(dev_port, qid):
    lane = dev_port % 4
    pg_queue = lane * 8 + qid # there are 8 queues per lane
    return pg_queue


def init_bfrt():
    global bfrt_endpoint
    global bfrt_port
    global bfrt_info
    global dev_tgt
    global dev_tgt_pipe0
    global interface
    global port_stat_table
    global queue_counters_table
    global byte_count_key
    global queue_usage_key
    global link_protect_table
    global link_protect_key
    global link_protect_data
    # for bfrt_client_id in range(10):
    try:
        interface = gc.ClientInterface(
            grpc_addr = str(bfrt_endpoint) + ":" + str(bfrt_port),
            client_id = BFRT_CLIENT_ID,
            device_id = 0,
            num_tries = 1)
        # break
    except:
        quit
    bfrt_info = interface.bfrt_info_get()
    # print('The target runs the program:', bfrt_info.p4_name_get())
    # if bfrt_client_id == 0:
    interface.bind_pipeline_config(bfrt_info.p4_name_get())
    dev_tgt = gc.Target(0)
    dev_tgt_pipe0 = gc.Target(0, 0)

    port_stat_table = bfrt_info.table_get('$PORT_STAT')
    queue_counters_table = bfrt_info.table_get('tf1.tm.counter.queue')
    queue_usage_key = queue_counters_table.make_key([gc.KeyTuple('pg_id', get_pg_id(TX_PROTECTED_PORT)), gc.KeyTuple('pg_queue', get_pg_queue(TX_PROTECTED_PORT, 0))])
    byte_count_key = port_stat_table.make_key([gc.KeyTuple('$DEV_PORT', END_POINT_SENDER_PORT)])
    link_protect_table = bfrt_info.table_get("SwitchEgress.link_protect")
    link_protect_key = [ link_protect_table.make_key([ gc.KeyTuple('eg_intr_md.egress_port', TX_PROTECTED_PORT) ]) ]
    link_protect_data = [ link_protect_table.make_data([ gc.DataTuple('dummy_pkt_max_count', 3), gc.DataTuple('blocking_mode', 1)], "SwitchEgress.protect")]


def log_speed_byte_counts(timestamp, byte_counts):
    fout_send_rate.write("{}\t{}\n".format(timestamp, byte_counts))


def poll_send_rate_byte_counts():
    global port_stat_table
    global byte_count_key
    print("Speed byte count polling started...")
    while not stop_polling_send_rate_byte_counts:
        # try: 
            response = port_stat_table.entry_get(dev_tgt, [byte_count_key], {'from_hw': True}, None)
            first_resp_entry = list(response)[0]  # only have 1 in this case
            # entry is a tuple: (data obj, key obj). Get the data obj and convert to a dict
            rx_port_stats = first_resp_entry[0].to_dict() 
            rx_octets = rx_port_stats['$OctetsReceived']
            log_speed_byte_counts(time.time(), rx_octets)
            time.sleep(0.100)
        # except KeyboardInterrupt:
        #     print("Interrupted!")
        #     break
    print("Speed byte count polling stopped!!")



def log_tx_buffer_usage(timestamp, usage, watermark, drop_count):
    fout_buffer.write("{}\t{}\t{}\t{}\n".format(timestamp, usage, watermark, drop_count))

def poll_tx_buffer_usage():
    global queue_counters_table
    global queue_usage_key
    is_protection_on = False
    start_time = time.time()
    
    print("Tx buffer polling started...")
    while not stop_polling_tx_buffer.is_set():
        # try:
            response = queue_counters_table.entry_get(dev_tgt_pipe0, [queue_usage_key], {'from_hw': False},  None)
            first_resp_entry = list(response)[0]  # only have 1 in this case
            tx_buffer_stats = first_resp_entry[0].to_dict()
            usage = tx_buffer_stats['usage_cells']
            watermark = tx_buffer_stats['watermark_cells']
            drop_count = tx_buffer_stats['drop_count_packets']
            log_tx_buffer_usage(time.time(), usage, watermark, drop_count)
            time.sleep(0.010)
            
            if is_protection_on == False:
                elapsed_time = time.time() - start_time
                if elapsed_time > 10:
                    enable_protection()
                    is_protection_on = True

        # except KeyboardInterrupt:
        #         print("Interrupted!")
        #         break
    print("Tx buffer polling stopped!!")


def enable_protection():
    try:
        link_protect_table.entry_add(dev_tgt, link_protect_key, link_protect_data)
    except gc.BfruntimeReadWriteRpcException:
        # pass
        link_protect_table.entry_mod(dev_tgt, link_protect_key, link_protect_data)

    print("Blocking mode protection enabled on devport {} on Tx switch".format(TX_PROTECTED_PORT))


def main():
    global tx_buffer_poll_thread
    init_bfrt()
    tx_buffer_poll_thread = threading.Thread(target=poll_tx_buffer_usage)
    print("Starting rx buffer poll thread...")
    tx_buffer_poll_thread.start()
    poll_send_rate_byte_counts()
    print("Output files:")
    print(send_rate_outfile)
    print(buff_outfile)
    
if __name__ == "__main__":
    main()
