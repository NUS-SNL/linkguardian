#!/usr/bin/env python3

import os
import sys

if len(sys.argv) != 2:  
    print("Usage: {} <RX_DEV_PORT>".format(sys.argv[0]))
    sys.exit(1)


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

RX_DEV_PORT_ON_REMOTE_SWITCH = int(sys.argv[1])
BFRT_CLIENT_ID = 99

bfrt_endpoint = 'tofino1c.d2.comp.nus.edu.sg'
bfrt_port = 50052
bfrt_info = None
dev_tgt = None
interface = None

def init_bfrt():
    global bfrt_endpoint
    global bfrt_port
    global bfrt_info
    global dev_tgt
    global interface
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

init_bfrt()

port_stat_table = bfrt_info.table_get('$PORT_STAT')
key = port_stat_table.make_key([gc.KeyTuple('$DEV_PORT', RX_DEV_PORT_ON_REMOTE_SWITCH)])

response = port_stat_table.entry_get(dev_tgt, [key], {'from_hw': False}, None)
first_resp_entry = list(response)[0]  # only have 1 in this case

# entry is a tuple: (data obj, key obj). Get the data obj and convert to a dict
rx_port_stats = first_resp_entry[0].to_dict() 

rx_ok = rx_port_stats['$FramesReceivedOK']

print(rx_ok)


