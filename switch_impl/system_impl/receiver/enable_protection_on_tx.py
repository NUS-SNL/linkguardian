#!/usr/bin/env python3

import os
import sys

# if len(sys.argv) != 3:  # TODO: take cmdline arguments
#     print("Usage: {} <rx_switch_ip/domain> <RX_DEV_PORT>")    

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

TX_DEV_PORT_ON_REMOTE_SWITCH = 32
BFRT_CLIENT_ID = 100

bfrt_endpoint = 'tofino1.d2.comp.nus.edu.sg'
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

link_protect_table = bfrt_info.table_get("SwitchEgress.link_protect")
link_protect_key = [ link_protect_table.make_key([ gc.KeyTuple('eg_intr_md.egress_port', TX_DEV_PORT_ON_REMOTE_SWITCH) ]) ]
link_protect_data = [ link_protect_table.make_data([ gc.DataTuple('dummy_pkt_max_count', 3), gc.DataTuple('blocking_mode', 1)], "SwitchEgress.protect")]

try:
    link_protect_table.entry_add(dev_tgt, link_protect_key, link_protect_data)
except gc.BfruntimeReadWriteRpcException:
    # pass
    link_protect_table.entry_mod(dev_tgt, link_protect_key, link_protect_data)

print("Blocking mode protection enabled on devport {} on Tx switch".format(TX_DEV_PORT_ON_REMOTE_SWITCH))
