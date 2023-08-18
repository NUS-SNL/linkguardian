#!/usr/bin/env python3

import sys
import os
import socket


if len(sys.argv) != 2:
    print("Usage: {} <link speed>".format(sys.argv[0]))
    sys.exit(1)

required_speed = int(sys.argv[1])

if required_speed not in [10, 25, 100]:
    print("Invalid link speed: {}".format(required_speed))
    sys.exit(1)

speed_to_speed_str = {10: 'BF_SPEED_10G', 25: 'BF_SPEED_25G', 100: 'BF_SPEED_100G'}

hostname = socket.gethostname()

devport_list = []

if hostname == "p4campus-proc1":
    devport_list = [36, 56, 128, 136, 160, 168]
elif hostname == "tofino1a":
    devport_list = [32, 36]
elif hostname == "tofino1c":
    devport_list = [36, 52]

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

def init_bfrt():
    global bfrt_endpoint
    global bfrt_port
    global bfrt_info
    global dev_tgt
    global dev_tgt_pipe0
    global interface
    global port_table
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

    port_table = bfrt_info.table_get('$PORT')
    
def main():
    init_bfrt()

    port_keys = []
    for devport in devport_list:
        port_keys.append(port_table.make_key([gc.KeyTuple('$DEV_PORT', devport)]))
    
    responses = port_table.entry_get(dev_tgt, port_keys, {'from_hw': True}, None)

    all_good = True
    for response in list(responses):
        # entry is a tuple: (data obj, key obj). Get the data obj and convert to a dict
        key = response[1].to_dict()
        port_cfg = response[0].to_dict() 
        curr_speed = port_cfg['$SPEED']
        port_up = port_cfg['$PORT_UP']

        if curr_speed != speed_to_speed_str[required_speed]:
            # print("Port {} is currently at speed {}, not {}".format(key['$DEV_PORT']['value'], curr_speed, speed_to_speed_str[required_speed]))
            all_good = False

        if not port_up:
            # print("Port {} is down".format(key['$DEV_PORT']['value']))
            all_good = False

    print(1 if all_good else 0)

if __name__ == "__main__":
    main()
