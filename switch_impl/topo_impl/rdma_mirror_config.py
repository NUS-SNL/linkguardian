################################################################################
# BAREFOOT NETWORKS CONFIDENTIAL & PROPRIETARY
#
# Copyright (c) 2019-present Barefoot Networks, Inc.
#
# All Rights Reserved.
#
# NOTICE: All information contained herein is, and remains the property of
# Barefoot Networks, Inc. and its suppliers, if any. The intellectual and
# technical concepts contained herein are proprietary to Barefoot Networks, Inc.
# and its suppliers and may be covered by U.S. and Foreign Patents, patents in
# process, and are protected by trade secret or copyright law.  Dissemination of
# this information or reproduction of this material is strictly forbidden unless
# prior written permission is obtained from Barefoot Networks, Inc.
#
# No warranty, explicit or implicit is provided, unless granted under a written
# agreement with Barefoot Networks, Inc.
#
################################################################################

import sys
import os
import argparse

sde_install = os.environ['SDE_INSTALL']
sys.path.append('%s/lib/python2.7/site-packages/tofino'%(sde_install))
sys.path.append('%s/lib/python2.7/site-packages/p4testutils'%(sde_install))
sys.path.append('%s/lib/python2.7/site-packages'%(sde_install))

import grpc
import time
from pprint import pprint
import bfrt_grpc.client as gc
import bfrt_grpc.bfruntime_pb2 as bfruntime_pb2
from functools import partial

# PORT_SNIFF = [147] # dv port for monitoring
PORT_SNIFF = [138] # dv port for monitoring
MIRROR_SESSION_ID = 777

def connect():
    # Connect to BfRt Server
    interface = gc.ClientInterface(grpc_addr='localhost:50052', client_id=0, device_id=0)
    target = gc.Target(device_id=0, pipe_id=0xFFFF)
    print('Connected to BfRt Server!')

    # Get the information about the running program
    bfrt_info = interface.bfrt_info_get()
    print('The target is running the', bfrt_info.p4_name_get())

    # Establish that you are working with this program
    interface.bind_pipeline_config(bfrt_info.p4_name_get())
    return interface, target, bfrt_info

def main():
    interface, target, bfrt_info = connect()

    # mirror_cfg_table
    mirror_cfg_table = bfrt_info.table_get("$mirror.cfg")
    
    mirror_cfg_bfrt_key  = mirror_cfg_table.make_key([gc.KeyTuple('$sid', MIRROR_SESSION_ID)])
    mirror_cfg_bfrt_data = mirror_cfg_table.make_data([
        gc.DataTuple('$direction', str_val="INGRESS"),
        gc.DataTuple('$ucast_egress_port', PORT_SNIFF[0]),
        gc.DataTuple('$ucast_egress_port_valid', bool_val=True),
        gc.DataTuple('$session_enable', bool_val=True),
    ], "$normal")
    try: 
        mirror_cfg_table.entry_add(target, [ mirror_cfg_bfrt_key ], [ mirror_cfg_bfrt_data ])
        print("Configuring mirror sessionID %d --> port %d is successful!" % (MIRROR_SESSION_ID, PORT_SNIFF[0]))
    except gc.BfruntimeRpcException as e:
        print("Unexpected Error: %s" % e)


if __name__ == '__main__':
    main()
