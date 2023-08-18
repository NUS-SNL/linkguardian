import asyncio
import async_timeout
import aioredis

import argparse
import time

from util import is_json, json_to_dict, dict_to_json, msg_corrupted

import os
import sys
import pdb

SDE_INSTALL   = os.environ['SDE_INSTALL']
SDE_PYTHON2   = os.path.join(SDE_INSTALL, 'lib', 'python2.7', 'site-packages')
sys.path.append(SDE_PYTHON2)
sys.path.append(os.path.join(SDE_PYTHON2, 'tofino'))
sys.path.append(os.path.join(SDE_PYTHON2, 'tofino', 'bfrt_grpc'))

PYTHON3_VER   = '{}.{}'.format(
    sys.version_info.major,
    sys.version_info.minor)
SDE_PYTHON3   = os.path.join(SDE_INSTALL, 'lib', 'python' + PYTHON3_VER,
                             'site-packages')
sys.path.append(SDE_PYTHON3)
sys.path.append(os.path.join(SDE_PYTHON3, 'tofino'))
sys.path.append(os.path.join(SDE_PYTHON3, 'tofino', 'bfrt_grpc'))

import bfrt_grpc.client as gc

bfrt_endpoint = None
bfrt_port = None
bfrt_info = None
dev_tgt = None

switch_id = None
sub_topic = None

blocking = False

r = None
pubsub = None
r_endpoint = None

topo = None
topo_ver = None

protected = None
protected_ver = None

loop = None

# THRESHOLDS
MONITORING_THRESHOLD = 10000000
LOSS_RATE_THRESHOLD = 1 / 1000000
LOSS_RATE_THRESHOLD_1 = 1e-6
LOSS_RATE_THRESHOLD_2 = 1e-3

# INTERNAL COUNTERS
rx_ok_offset = dict()
rx_ok_window = dict()
rx_all_offset = dict()
rx_all_window = dict()

async def get_upstream(sw, dp):
    global topo
    global topo_ver

    curr_ver = await r.get('topo_ver')
    if not curr_ver:
        return -1, -1, -1 
    print("curr_ver", str(curr_ver, 'utf-8'))
    
    if curr_ver != topo_ver:
        topo_ver = curr_ver
        topo_json = await r.get('topo')
        if not topo_json:
            return -1, -1, -1
        print(str(topo_json, 'utf-8'))
        topo = json_to_dict(str(topo_json, 'utf-8'))

    lookup_key = str(sw) + "-" + str(dp)
    if not lookup_key in topo:
        return -1, -1, -1

    upstream = topo[lookup_key].split("-")
    up_sw = int(upstream[0])
    up_dp = int(upstream[1])
    up_mcast = int(upstream[2])
    return up_sw, up_dp, up_mcast

def is_link_bad(loss_rate):
    return loss_rate >= LOSS_RATE_THRESHOLD_1

#def is_link_bad(frames_rx_ok, frames_rx_all):
#    return True # for testing
#    if frames_rx_all <= MONITORING_THRESHOLD:
#        return False
#    else:
#        loss_rate = compute_loss_rate(frames_rx_ok, frames_rx_all)
#        return loss_rate >= LOSS_RATE_THRESHOLD

def compute_loss_rate(frames_rx_ok, frames_rx_all):
    if frames_rx_all == 0:
        return 0
    return 1 - (frames_rx_ok / frames_rx_all)

def loss_rate_to_action(loss_rate):
    if loss_rate >= LOSS_RATE_THRESHOLD_2:
        return 2 # mcast
    if loss_rate >= LOSS_RATE_THRESHOLD_1:
        return 1 # ucast
    return -1

# def loss_rate_to_dummy(loss_rate):
#     if loss_rate >= 0.01:
#         return 1
#     if loss_rate >= 0.0001:
#         return 2
#     return 3

# async def activate_link_guardian(dev_port, dummy_packets):
#     print("activate link guardian at sw", switch_id, "dev_port", dev_port, "dummy_pkts", dummy_packets)

#     link_protect_table = bfrt_info.table_get("SwitchEgress.link_protect")
#     key = [ link_protect_table.make_key([ gc.KeyTuple('eg_intr_md.egress_port', dev_port) ]) ]
#     data = [ link_protect_table.make_data([ gc.DataTuple('dummy_pkt_max_count', dummy_packets), gc.DataTuple('blocking_mode', 0)], "SwitchEgress.protect")]

#     try:
#         link_protect_table.entry_add(dev_tgt, key, data)
#     except gc.BfruntimeReadWriteRpcException:
#         link_protect_table.entry_mod(dev_tgt, key, data)
    
#     lookup_key = "protected-" + str(switch_id) + "-" + str(dev_port)
#     await r.set(lookup_key, dummy_packets)

async def activate_link_guardian(dev_port, action, mcast_grp):
    print("activate link guardian at sw:", switch_id, "dev_port:", dev_port, "action type:", action)
    
    blocking_mode = 1 if blocking else 0

    link_protect_table = bfrt_info.table_get("SwitchEgress.link_protect")
    link_protect_key = [ link_protect_table.make_key([ gc.KeyTuple('eg_intr_md.egress_port', dev_port) ]) ]
    link_protect_data = [ link_protect_table.make_data([ gc.DataTuple('dummy_pkt_max_count', 1), gc.DataTuple('blocking_mode', 0)], "SwitchEgress.protect")]

    retx_table = bfrt_info.table_get("SwitchIngress.retx_mcast_buffered_pkt")
    retx_key = [ retx_table.make_key([ gc.KeyTuple('hdr.linkradar_buffered.dst_eg_port', dev_port) ]) ]
    if action == 1:
        retx_data = [ retx_table.make_data([], "SwitchIngress.do_retx_buffered_pkt_ucast") ] 
    else:
        retx_data = [ retx_table.make_data([ gc.DataTuple('grp_id', mcast_grp) ], "SwitchIngress.do_retx_buffered_pkt_mcast") ]

    try:
        link_protect_table.entry_add(dev_tgt, link_protect_key, link_protect_data)
    except gc.BfruntimeReadWriteRpcException:
        # pass
        link_protect_table.entry_mod(dev_tgt, link_protect_key, link_protect_data)

    try:
        retx_table.entry_add(dev_tgt, retx_key, retx_data)
    except gc.BfruntimeReadWriteRpcException:
        retx_table.entry_mod(dev_tgt, retx_key, retx_data)
    
    lookup_key = "protected-" + str(switch_id) + "-" + str(dev_port)
    await r.set(lookup_key, action)

async def process_msg(json_str):
    j = json_to_dict(json_str)
    event = j['event']
    sw_id = j['switch_id']
    dp = j['dev_port']
    mcast_grp = j['mcast_grp']
    action = j['action']

    assert event == sub_topic
    assert sw_id == switch_id

    await activate_link_guardian(dp, action, mcast_grp)

async def is_protected(sw, dp, action):
    keys = await r.keys("protected*")
    keys = [str(k, 'utf-8') for k in keys ]
    print(keys)
    lookup_key = "protected-" + str(sw) + "-" + str(dp)

    if not lookup_key in keys:
        return False
    
    curr_action = int(await r.get(lookup_key))
    if action > curr_action:
        return False
    return True

# async def is_protected(sw, dp, dummy_pkts):
#     keys = await r.keys("protected*")
#     keys = [str(k, 'utf-8') for k in keys ]
#     print(keys)
#     lookup_key = "protected-" + str(sw) + "-" + str(dp)

#     if not lookup_key in keys:
#         return False
    
#     curr_dummy = int(await r.get(lookup_key))
#     if curr_dummy > dummy_pkts:
#         return False
#     return True


async def poll_counters():
    print('Starting polling coroutine')
    await asyncio.sleep(5.0)

    global rx_ok_offset
    global rx_ok_window
    global rx_all_offset
    global rx_all_window

    while True:
        print("time", time.time())

        port_table = bfrt_info.table_get('$PORT')
        resp = list(port_table.entry_get(dev_tgt, [], {'from_hw': True}, None))
        dev_ports = [ res[1].to_dict()['$DEV_PORT']['value'] for res in resp if res[0]['$PORT_UP'].bool_val ]
        print(dev_ports)

        port_stat_table = bfrt_info.table_get('$PORT_STAT')
        keys = [ port_stat_table.make_key([gc.KeyTuple('$DEV_PORT', dp)]) for dp in dev_ports ]
        resp = list(port_stat_table.entry_get(dev_tgt, keys, {'from_hw': False}, None))
        for i, res in enumerate(resp):
            data_dict = res[0].to_dict()
            frames_rx_ok = data_dict['$FramesReceivedOK']
            frames_rx_all = data_dict['$FramesReceivedAll']
            
            if not dev_ports[i] in rx_all_offset:
                rx_all_offset[dev_ports[i]] = 0
            if not dev_ports[i] in rx_ok_offset:
                rx_ok_offset[dev_ports[i]] = 0
            
            # just to init the values
            if rx_ok_offset[dev_ports[i]] == 0:
                rx_ok_offset[dev_ports[i]] = frames_rx_ok
            if rx_all_offset[dev_ports[i]] == 0:
                rx_all_offset[dev_ports[i]] = frames_rx_all

            # moving window logic
            # compute the delta
            # then update the offsets
            rx_ok_delta = frames_rx_ok - rx_ok_offset[dev_ports[i]]
            rx_all_delta = frames_rx_all - rx_all_offset[dev_ports[i]]
            
            if not dev_ports[i] in rx_ok_window:
                rx_ok_window[dev_ports[i]] = []
            if not dev_ports[i] in rx_all_window:
                rx_all_window[dev_ports[i]] = []
            
            rx_ok_window[dev_ports[i]].append(rx_ok_delta)
            rx_all_window[dev_ports[i]].append(rx_all_delta)

            rx_ok_offset[dev_ports[i]] = frames_rx_ok
            rx_all_offset[dev_ports[i]] = frames_rx_all

            print(">>> curr sw dp", dev_ports[i])
            print("frames_rx_ok", frames_rx_ok, "frames_rx_all", frames_rx_all)
            print("rx_ok_offset", rx_ok_offset[dev_ports[i]], "rx_all_offset", rx_all_offset[dev_ports[i]])
            print("rx_ok_delta", rx_ok_delta, "rx_all_delta", rx_all_delta, "loss rate", compute_loss_rate(sum(rx_ok_window[dev_ports[i]]), sum(rx_all_window[dev_ports[i]])))
            print(">>>")

            if sum(rx_all_window[dev_ports[i]]) > MONITORING_THRESHOLD:
                loss_rate = compute_loss_rate(sum(rx_ok_window[dev_ports[i]]), sum(rx_all_window[dev_ports[i]]))
                while sum(rx_all_window[dev_ports[i]]) > MONITORING_THRESHOLD:
                    rx_all_window[dev_ports[i]].pop()
                    rx_ok_window[dev_ports[i]].pop()
            # if rx_all_delta > MONITORING_THRESHOLD:
            #     loss_rate = compute_loss_rate(rx_ok_delta, rx_all_delta)
            #     tmp = rx_all_delta - MONITORING_THRESHOLD
            #     rx_all_offset[dev_ports[i]] += tmp

            #     if rx_ok_offset[dev_ports[i]] + (tmp - (rx_all_delta - rx_ok_delta)) > frames_rx_ok:    
            #         rx_ok_offset[dev_ports[i]] = frames_rx_ok
            #     else:
            #         rx_ok_offset[dev_ports[i]] += (tmp - (rx_all_delta - rx_ok_delta)) 
                # rx_all_offset += rx_all_delta
                # rx_ok_offset += rx_all_delta
                
                bad_link = is_link_bad(loss_rate)
                if bad_link:
                    action = loss_rate_to_action(loss_rate)
                    print("bad link:", dev_ports[i], "rx_ok_delta", rx_ok_delta, "rx_all_delta", rx_all_delta, "loss_rate", loss_rate)
                    sw, dp, mcast_grp = await get_upstream(switch_id, dev_ports[i])
                    print(sw, dp, mcast_grp)
                    if (sw, dp) == (-1, -1, -1):
                        print("invalid upstream link, please update the topology using tools.py")
                        continue
                    if not await is_protected(sw, dp, action):
                        topic = "SWITCH-" + str(sw)
                        await r.publish(topic, dict_to_json(msg_corrupted(topic, sw, dp, mcast_grp, action)))

                # bad_link = is_link_bad(frames_rx_ok, frames_rx_all)
                # loss_rate = compute_loss_rate(frames_rx_ok, frames_rx_all)
                # dummy_packets = loss_rate_to_dummy(loss_rate)

                # if bad_link:
                #     print("bad link", dev_ports[i], frames_rx_ok, frames_rx_all)
                #     sw, dp = await get_upstream(switch_id, dev_ports[i])
                #     print(sw, dp)
                #     if (sw, dp) == (-1, -1):
                #         print("invalid upstream link, please update the topology using tools.py")
                #         continue
                #     if not await is_protected(sw, dp, dummy_packets):
                #         topic = "SWITCH-" + str(sw)
                #         await r.publish(topic, dict_to_json(msg_corrupted(topic, sw, dp, dummy_packets)))
        await asyncio.sleep(1.0)

async def reader(channel: aioredis.client.PubSub):
    print('>> Starting reader coroutine <<')
    while True:
        try:
            async with async_timeout.timeout(1):
                message = await channel.get_message(ignore_subscribe_messages=True)
                if message is not None:
                    print(f"(Reader) Message Received: {message}")
                    data = message["data"]
                    if is_json(data):
                        await process_msg(data)
                await asyncio.sleep(0.01)
        except asyncio.TimeoutError:
            pass

async def init_redis():
    global r 
    global pubsub

    r = await aioredis.from_url("redis://" + str(r_endpoint))
    pubsub = r.pubsub()
    await pubsub.subscribe(sub_topic)
    # await pubsub.psubscribe("SWITCH*")
    
    try:
        future = asyncio.create_task(reader(pubsub))
    except AttributeError:
        future = asyncio.ensure_future(reader(pubsub), loop=loop)
    await future

async def init_bfrt():
    global bfrt_endpoint
    global bfrt_port
    global bfrt_info
    global dev_tgt

    for bfrt_client_id in range(10):
        try:
            interface = gc.ClientInterface(
                grpc_addr = str(bfrt_endpoint) + ":" + str(bfrt_port),
                client_id = bfrt_client_id,
                device_id = 0,
                num_tries = 1)
            break
        except:
            quit
    bfrt_info = interface.bfrt_info_get()
    print('The target runs the program ', bfrt_info.p4_name_get())

    if bfrt_client_id == 0:
        interface.bind_pipeline_config(bfrt_info.p4_name_get())
    dev_tgt = gc.Target(0)

async def main():
    if PYTHON3_VER < '3.7':
        asyncio.ensure_future(init_redis(), loop=loop)        
    else:
        await init_redis()
    await init_bfrt()
    await poll_counters()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--id', type=int, required=True,
        help='switch id'
    )

    parser.add_argument(
        '--redis-endpoint', required=False, default='localhost',
        help='redis endpoint'
    )

    parser.add_argument(
        '--bfrt-endpoint', required=False, default='localhost',
        help='bft endpoint'
    )

    parser.add_argument(
        '--bfrt-port', type=int, required=False, default=50052,
        help='bfrt port'
    )

    parser.add_argument(
        '--blocking', default=False, action='store_true',
        help='enable blocking mode'
    )

    args = parser.parse_args()
    switch_id = args.id
    sub_topic = "SWITCH-" + str(switch_id)
    r_endpoint = args.redis_endpoint
    bfrt_endpoint = args.bfrt_endpoint
    bfrt_port = args.bfrt_port
    blocking = args.blocking 

    if PYTHON3_VER > '3.7':
        asyncio.run(main(sub_topic))
    else:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
