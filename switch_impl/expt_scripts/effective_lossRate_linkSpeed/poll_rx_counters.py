#!/usr/bin/env python3

from glob import glob
import os
import sys
import time
import threading
import signal
import socket
import getpass


RECIRC_PORT_PIPE_0 = 20
SLEEP_FOR_FORWARDING_TRAFFIC_COUNTERS = 0.1

hostname = socket.gethostname()
stop_polling_rx_buffer = threading.Event()
rx_buffer_poll_thread = None
stop_polling_speed_byte_counts = False
fout_speed = None
fout_buffer = None
speed_outfile = None
buff_outfile = None

if len(sys.argv) != 4:  # TODO: take cmdline arguments
    print("Usage: {} <expt_name> <0/1: poll rx buffer> <0/1: s2s or endhost>".format(sys.argv[0]))    
    sys.exit(1)


if int(sys.argv[2]) == 1:
    poll_rx_buffer = True
else:
    poll_rx_buffer = False


def cleanup():
    global stop_polling_speed_byte_counts
    print("Stopping rx buffer poll thread...")
    stop_polling_rx_buffer.set()
    print("Stopping speed byte counts polling...")
    stop_polling_speed_byte_counts = True
    if poll_rx_buffer:
        rx_buffer_poll_thread.join()

def signal_handler(sig, frame):
    print('Caught Ctrl+C!')
    print("Stopping and cleaning up...")
    cleanup()

signal.signal(signal.SIGINT, signal_handler)


expt_name = sys.argv[1]
expt_type = int(sys.argv[3])

if expt_type not in [0,1]:
    print("third arg should be: 0/1: s2s or endhost")
    sys.exit(1)


if expt_type == 0: # s2s
    OUTPATH = "/home/{}/traces/effective_lossRate_linkSpeed".format(getpass.getuser())
    if not os.path.exists(OUTPATH):
        print("WARN: Output directory '{}' does not exist".format(OUTPATH))
        print("Creating the same ...")
        try:
            os.makedirs(OUTPATH, mode=0o775, exist_ok=True)
        except Exception as e:
            print(str(e))
            sys.exit(1)
    if hostname == 'tofino1c':
        FORWARDING_PORT_TO_POLL = 52
    elif hostname == 'tofino1b':
        FORWARDING_PORT_TO_POLL = 172
    elif hostname == 'p4campus-proc1':
        FORWARDING_PORT_TO_POLL = 168
elif expt_type == 1: # endhost
    OUTPATH = "/home/cirlab/traces/congestion_signal_expts"
    FORWARDING_PORT_TO_POLL = 28

stop_polling_rx_buffer.clear()

speed_outfile = OUTPATH + "/{}_forwarded_byte_counts.dat".format(expt_name)
buff_outfile = OUTPATH + "/{}_rx_buff.dat".format(expt_name)

fout_speed = open(speed_outfile, "w")
fout_buffer = None

if poll_rx_buffer:
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
sys.path.reverse() # to make the SDE 9.11.2 paths come earlier for p4campus-proc1

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
    queue_usage_key = queue_counters_table.make_key([gc.KeyTuple('pg_id', get_pg_id(RECIRC_PORT_PIPE_0)), gc.KeyTuple('pg_queue', get_pg_queue(RECIRC_PORT_PIPE_0, 0))])
    byte_count_key = port_stat_table.make_key([gc.KeyTuple('$DEV_PORT', FORWARDING_PORT_TO_POLL)])


def log_speed_byte_counts(timestamp, byte_counts):
    fout_speed.write("{}\t{}\n".format(timestamp, byte_counts))


def poll_speed_byte_counts():
    global port_stat_table
    global byte_count_key
    print("Speed byte count polling started...")
    while not stop_polling_speed_byte_counts:
        # try: 
            response = port_stat_table.entry_get(dev_tgt, [byte_count_key], {'from_hw': True}, None)
            first_resp_entry = list(response)[0]  # only have 1 in this case
            # entry is a tuple: (data obj, key obj). Get the data obj and convert to a dict
            rx_port_stats = first_resp_entry[0].to_dict() 
            tx_octets = rx_port_stats['$OctetsTransmittedTotal']
            log_speed_byte_counts(time.time(), tx_octets)
            time.sleep(SLEEP_FOR_FORWARDING_TRAFFIC_COUNTERS)
        # except KeyboardInterrupt:
        #     print("Interrupted!")
        #     break
    print("Speed byte count polling stopped!!")



def log_rx_buffer_usage(timestamp, usage, watermark, drop_count):
    fout_buffer.write("{}\t{}\t{}\t{}\n".format(timestamp, usage, watermark, drop_count))

def poll_rx_buffer_usage():
    global queue_counters_table
    global queue_usage_key
    
    print("Rx buffer polling started...")
    while not stop_polling_rx_buffer.is_set():
        # try:
            response = queue_counters_table.entry_get(dev_tgt_pipe0, [queue_usage_key], {'from_hw': True},  None)
            timestamp = time.time()
            first_resp_entry = list(response)[0]  # only have 1 in this case
            rx_buffer_stats = first_resp_entry[0].to_dict()
            usage = rx_buffer_stats['usage_cells']
            watermark = rx_buffer_stats['watermark_cells']
            drop_count = rx_buffer_stats['drop_count_packets']
            log_rx_buffer_usage(timestamp, usage, watermark, drop_count)
            time.sleep(0.010)
        # except KeyboardInterrupt:
        #         print("Interrupted!")
        #         break
    print("Rx buffer polling stopped!!")


def main():
    global rx_buffer_poll_thread
    init_bfrt()
    if poll_rx_buffer:
        rx_buffer_poll_thread = threading.Thread(target=poll_rx_buffer_usage)
        print("Starting rx buffer poll thread...")
        rx_buffer_poll_thread.start()
    poll_speed_byte_counts()
    print("Output files:")
    print(speed_outfile)
    print(buff_outfile)
    
if __name__ == "__main__":
    main()
