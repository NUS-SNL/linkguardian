#!/usr/bin/env python3

import os
import sys

# if len(sys.argv) != 3:  # TODO: take cmdline arguments
#     print("Usage: {} <rx_switch_ip/domain> <RX_DEV_PORT>")   

if len(sys.argv) != 2:  # TODO: take cmdline arguments
    print("Usage:<python_interpreter> {} <nb_mode: 0 or 1>".format(sys.argv[0]))    
    sys.exit(1)

nb_mode = int(sys.argv[1])

# THIS IS A HACK. NEEDED WHEN THE TOPO.P4 IS RUNNING ON P4CAMPUS-PROC1
# PROC1 IS RUNNING SDE 9.11.X WHOSE BFRT_GRPC DOESN'T WORK WITH SDE 9.10.X CLIENT
# SO WE MANUALLY OVERRIDE TO USE SDE 9.11.2 ON TOFINO1A FOR THE CLIENT

# SDE_INSTALL = os.environ['SDE_INSTALL'] # when topo.p4 on tofino1b
SDE_INSTALL = '/home/cirlab/bf-sde-9.11.2/install' # when topo.p4 on p4campus-proc1
PYTHON3_VER = '{}.{}'.format(
    sys.version_info.major,
    sys.version_info.minor)
SDE_PYTHON3 = os.path.join(SDE_INSTALL, 'lib', 'python' + PYTHON3_VER,
                             'site-packages')
sys.path.append(SDE_PYTHON3)
sys.path.append(os.path.join(SDE_PYTHON3, 'tofino'))
sys.path.append(os.path.join(SDE_PYTHON3, 'tofino', 'bfrt_grpc'))
sys.path.reverse() # to make the SDE 9.11.2 paths come earlier

import bfrt_grpc.client as gc

BFRT_CLIENT_ID = 99

if nb_mode == 1:
    bfrt_endpoint = 'p4campus-proc1.d2.comp.nus.edu.sg'
    TX_DEV_PORT_ON_REMOTE_SWITCH = 168
    # bfrt_endpoint = 'tofino1b.d2.comp.nus.edu.sg'
    # TX_DEV_PORT_ON_REMOTE_SWITCH = 172
else:
    bfrt_endpoint = 'tofino1c.d2.comp.nus.edu.sg'
    TX_DEV_PORT_ON_REMOTE_SWITCH = 52

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
    except Exception:
        quit
    bfrt_info = interface.bfrt_info_get()
    # print('The target runs the program:', bfrt_info.p4_name_get())
    # if bfrt_client_id == 0:
    interface.bind_pipeline_config(bfrt_info.p4_name_get())
    dev_tgt = gc.Target(0)

init_bfrt()

port_stat_table = bfrt_info.table_get('$PORT_STAT')
key = port_stat_table.make_key([gc.KeyTuple('$DEV_PORT', TX_DEV_PORT_ON_REMOTE_SWITCH)])

response = port_stat_table.entry_get(dev_tgt, [key], {'from_hw': False}, None)
first_resp_entry = list(response)[0]  # only have 1 in this case

# entry is a tuple: (data obj, key obj). Get the data obj and convert to a dict
tx_port_stats = first_resp_entry[0].to_dict() 

tx_count = tx_port_stats['$FramesTransmittedAll']

print(tx_count)

