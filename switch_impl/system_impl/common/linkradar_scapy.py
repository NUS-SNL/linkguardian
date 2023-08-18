from multiprocessing import dummy
from scapy.all import *
import re

LINKRADAR_HDR_TYPE_DATA = 0b00
LINKRADAR_HDR_TYPE_LACK = 0b01
LINKRADAR_HDR_TYPE_LOSS_NOTIFY = 0b10
LINKRADAR_HDR_TYPE_TX_BUFFERED = 0b11
COURIER_PKT_QID = DUMMY_PKT_QID = 1

MTU_PKT_LENGTH = 1514
SMALLEST_PKT_LENGTH = 60
LUMOS_DEVTEST_IFACE = "ens3f0"
TINA_DEVTEST_IFACE = "enp129s0f0"
TOFINO_CPU_PCIE_IFACE = "ens1"

def mac_int_to_str(mac_int):
    return  ":".join(re.findall("..", "%012x" % mac_int))

# class LinkRadarType(Packet):
#     name = 'linkradar_type'
#     fields_desc = [
#         BitField("type", 0, 2),
#     ]


class LinkRadarData(Packet):
    name = 'linkradar_data'
    fields_desc = [
        BitField("type", LINKRADAR_HDR_TYPE_DATA, 2),
        BitField("_pad", 0, 1),
        BitField("era", 0, 1),
        BitField("retx", 0, 1), # name, default value, size
        BitField("dummy", 0, 1),
        BitField("blocking_mode", 0, 1),
        BitField("rx_buffered", 0, 1),
        ShortField("seq_no", None)
    ]

bind_layers(Ether, LinkRadarData, type=0xABCD)

# bind_layers(LinkRadarType, LinkRadarData, type=LINKRADAR_HDR_TYPE_DATA)

class LinkRadarLack(Packet):
    name = 'linkradar_lack'
    fields_desc = [
        BitField("type", LINKRADAR_HDR_TYPE_LACK, 2),
        BitField("is_piggy_backed", 0, 1),
        BitField("era", 0, 1), # name, default value, size
        BitField("_pad", 0, 4),
        ShortField("seq_no", None)
    ]

bind_layers(Ether, LinkRadarLack, type=0xABCD)
# bind_layers(LinkRadarType, LinkRadarLack, type=LINKRADAR_HDR_TYPE_LACK)


class LinkRadarBuffered(Packet):
    name = 'linkradar_buffered'
    fields_desc = [
        BitField("type", LINKRADAR_HDR_TYPE_TX_BUFFERED, 2),
        BitField("_pad_count", 0, 5),
        BitField("dst_eg_port", 0, 9), # name, default value, size
    ]

bind_layers(Ether, LinkRadarBuffered, type=0xABCD)

class LinkRadarRxBuffered(Packet):
    name = 'linkradar_rx_buffered'
    fields_desc = [
        ByteField("orig_ig_port", 0)
    ]

bind_layers(LinkRadarData, LinkRadarRxBuffered, rx_buffered = 1)

##############################################


def retransmit(seq):
    pkt = Ether(dst="AA:BB:CC:DD:EE:FF",src="b8:ce:f6:04:6b:d0")/LinkRadarData(seq_no=seq, retx=1)
    pkt = pkt / IP() / TCP()
    pkt = pkt / Raw(load=bytearray(MTU_PKT_LENGTH - len(pkt)))

    sendp(pkt, iface=LUMOS_DEVTEST_IFACE)


def send_normal_pkt(interface=TINA_DEVTEST_IFACE, app_seq_no=0):
    pkt = Ether(dst="b8:ce:f6:04:6c:04",src="b8:ce:f6:04:6b:d0")
    pkt = pkt / IP() / TCP()
    pkt = pkt / Raw(load=str(app_seq_no).encode('utf-8'))
    pkt = pkt / Raw(load=bytearray(MTU_PKT_LENGTH - len(pkt)))
    sendp(pkt, iface=interface)


def send_initial_courier_pkt(dev_port):
    dst_mac_addr = (dev_port << 5) | COURIER_PKT_QID
    pkt = Ether(dst=mac_int_to_str(dst_mac_addr),src="b8:ce:f6:04:6b:d0")/LinkRadarLack(seq_no=0, era=0)
    pkt = pkt / IP() / TCP()
    pkt = pkt / Raw(load=bytearray(SMALLEST_PKT_LENGTH - len(pkt)))
    sendp(pkt, iface=TOFINO_CPU_PCIE_IFACE, verbose=0)
    print("Sent init courier pkt on eg_port {}. Pkt length: {}".format(dev_port, len(pkt)))

def send_initial_dummy_pkt(dev_port):
    dst_mac_addr = (dev_port << 5) | DUMMY_PKT_QID
    pkt = Ether(dst=mac_int_to_str(dst_mac_addr),src="b8:ce:f6:04:6b:d0")/LinkRadarData(seq_no=0, era=0, retx=0, dummy=1)
    pkt = pkt / IP() / UDP()
    pkt = pkt / Raw(load=bytearray(SMALLEST_PKT_LENGTH - len(pkt)))
    sendp(pkt, iface=TOFINO_CPU_PCIE_IFACE, verbose=0)
    print("Sent init dummy pkt on eg_port {}. Pkt length: {}".format(dev_port, len(pkt)))

def send_buffered_pkt(eg_port, seq, era, interface=TINA_DEVTEST_IFACE):
    pkt = Ether(dst="AA:BB:CC:DD:EE:FF",src="b8:ce:f6:04:6b:d0")/LinkRadarBuffered(dst_eg_port=eg_port)
    pkt = pkt / LinkRadarData(seq_no=seq, era=era, retx=0)
    pkt = pkt / IP() / TCP()
    pkt = pkt / Raw(load=bytearray(MTU_PKT_LENGTH - len(pkt)))

    sendp(pkt, iface=interface)


def send_dummy_pkt(seq, era, interface=TINA_DEVTEST_IFACE):
    pkt = Ether(dst="AA:BB:CC:DD:EE:FF",src="b8:ce:f6:04:6b:d0")
    pkt = pkt / LinkRadarData(seq_no=seq, era=era, retx=0, dummy=1)
    pkt = pkt / IP() / UDP()
    pkt = pkt / Raw(load=bytearray(SMALLEST_PKT_LENGTH - len(pkt)))
    sendp(pkt, iface=interface)


def send_linkradar_data_pkt(seq, era, blocking_mode, interface=TINA_DEVTEST_IFACE, retx=0):
    # pkt = Ether(dst="AA:BB:CC:DD:EE:FF",src="b8:ce:f6:04:6b:d0")
    pkt = Ether(dst="b8:ce:f6:04:6c:04",src="b8:ce:f6:04:6b:d0")
    # pkt = Ether(dst="b8:ce:f6:04:6c:05",src="b8:ce:f6:04:6b:d1")
    pkt = pkt / LinkRadarData(seq_no=seq, era=era, retx=retx, blocking_mode=blocking_mode, dummy=0)
    pkt = pkt / IP() / TCP()
    seq_no_str = str(seq)
    pkt = pkt / Raw(load=seq_no_str.encode('utf-8'))
    pkt = pkt / Raw(load=bytearray(MTU_PKT_LENGTH - len(pkt)))
    sendp(pkt, iface=interface)


def get_linkradar_rx_buffered_pkt(seq, era, frame_size=79): 
    # frame size (including FCS) of 79 gives pkt occupying exactly 1 cell
    pkt = Ether(dst="10:70:fd:b3:5e:6f", src="10:70:fd:b3:61:8f")  # patronus ==> knowhere
    pkt = pkt / LinkRadarData(seq_no=seq, era=era, retx=0, blocking_mode=1, dummy=0, rx_buffered=1)
    pkt = pkt / LinkRadarRxBuffered(orig_ig_port=36)
    pkt = pkt / IP() / TCP()
    seq_no_str = str(seq)
    pkt = pkt / Raw(load=seq_no_str.encode('utf-8'))
    size_without_fcs = frame_size - 4 
    pkt = pkt / Raw(load=bytearray(size_without_fcs - len(pkt)))
    return pkt

def send_linkradar_rx_buffered_pkt(seq, era, size=72, interface=LUMOS_DEVTEST_IFACE):
    pkt = get_linkradar_rx_buffered_pkt(seq, era, size)
    sendp(pkt, iface=interface)

# On knowhere:
# send_linkradar_rx_buffered_pkt(next_seq_no, 0, "ens4f1")


# For Rx buffer/pfc testing from knowhere
""" 
interface = "ens4f1"
pkt_list = []
for i in range(10001,11001):
    pkt = get_linkradar_rx_buffered_pkt(i, 0, 1522)
    pkt_list.append(pkt)

# To load first 10 pkts
for pkt in pkt_list[:10]: 
    sendp(pkt, iface=interface)
"""

