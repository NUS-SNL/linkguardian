import sys
from scapy.all import *
import time

ETHERTYPE = 0xBFBF  # used to identify pktgen pkt
SRC_MAC = "BF:CC:11:22:33:44"  # doesn't matter


RDMA_WRITE_MIDDLE_PKT_SIZE = 1082
NORMAL_TCP_MTU_PKT_SIZE = 1514

PKT_LENGTH = NORMAL_TCP_MTU_PKT_SIZE # 1514 # 60, 124, 508, 1020, 1514

TIME_PERIOD_10G = 1240
TIME_PERIOD_25G = 496
TIME_PERIOD_50G = 248
TIME_PERIOD_100G = 124 # 123 for pfc pause-resume measurement
TIME_PERIOD = TIME_PERIOD_100G  # 1ms  | IPG for 1514B pkts @100G = 123.04ns

def make_port(pipe, local_port):
    assert pipe >= 0 and pipe < 4
    assert local_port >= 0 and local_port < 72
    return pipe << 7 | local_port

PKTS_COUNT = 1

# FORM an IP packet to be written to buffer
pkt = Ether(dst="01:02:03:04:05:06", src=SRC_MAC, type=ETHERTYPE)
pkt = pkt / IP(proto=144)  # / TCP()
pkt = pkt / Raw(load=bytearray(PKT_LENGTH - len(pkt)))

hexdump(pkt)

# Write the packet to the pktgen buffer
# skip the first 6 bytes for pktgen header
pktgen.write_pkt_buffer(0, len(pkt) - 6, bytes(pkt)[6:]) # buffer offset, buffer size, buffer data

# enable pktgen on pipe 1's port 68 (100Gbps)
pktgen.enable(make_port(1, 68))  # port 196

# create the app configuration
app_cfg = pktgen.AppCfg_t()
app_cfg.trigger_type = pktgen.TriggerType_t.TIMER_PERIODIC
app_cfg.timer = TIME_PERIOD 
app_cfg.batch_count = 0 # sets no. of batches that we want to have; the batch_id field of pktgen header keeps incrementing until this value is reached
app_cfg.pkt_count = PKTS_COUNT - 1 # sets no. of packets that we want to have in a batch; the packet_id field of pktgen header keeps incrementing until this value is reached. We are doing -1 in the above case because the numbering is starting from 0. pkt_count = 0 means 1 pkt per batch and batch_count = 0 means 1 batch per trigger
app_cfg.src_port = 68   # pipe local src port
app_cfg.buffer_offset = 0
app_cfg.length = len(pkt) - 6

# configure app id 5 with the app config
pktgen.cfg_app(1, app_cfg)
conn_mgr.complete_operations()

# -------------------- DO *NOT* START PKTGEN TRAFFIC-------------- #
# pktgen.app_enable(1)
print("PktGen Configured!! Packet size: {} bytes".format(len(pkt)))
# pktgen.app_disable(1)
# pktgen.show_counters(same=True)


# ----------- ENABLE LINK FLOW CONTROL ----------- #
# Enabling and checking link pause on devport 32
# pal.port_flow_control_link_pause_set(32, 1, 1)
# pal.port_flow_control_link_pause_get(32)

# Enabling and checking link PFC on devport 32
pal.port_flow_control_pfc_set(32, 0xff, 0xff) # devport, tx_en_map, rx_en_map
pal.port_flow_control_pfc_get(32)
tm.set_q_pfc_cos_mapping(32, 0, 1) # devport 32, tm qid 0, set egress_cos to 1

# Making the port 0 queue static to 7000 cells. baf=9 disables dynamic buffer use
tm.set_q_app_pool_usage(32, 0, pool=4, base_use_limit=7000, dynamic_baf=9, hysteresis=32)

# For reTx latency and effective loss rate measurement. Make it to 200 cells.
# tm.set_q_app_pool_usage(32, 0, pool=4, base_use_limit=200, dynamic_baf=9, hysteresis=32)
