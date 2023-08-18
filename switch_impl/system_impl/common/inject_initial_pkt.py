import socket
import sys

hostname = socket.gethostname()

linkradar_common_path = ""

if hostname == "tofino1a" or hostname == "tofino1c":
    linkradar_common_path = "/home/cirlab/jarvis-tofino/linkradar/system_impl/common"
elif hostname == "hep":
    linkradar_common_path = "/home/tofino/jarvis-tofino/linkradar/system_impl/common"
else:
    print("ERROR: invalid host {}".format(hostname))
    sys.exit(1)

sys.path.append(linkradar_common_path)

from linkradar_scapy import *

if len(sys.argv) != 3:
    print("Usage: {} <pkt type: dummy/courier> <eg_port>".format(sys.argv[0]))
    sys.exit(1)


pkt_type = sys.argv[1]
eg_port = int(sys.argv[2])

if pkt_type == "dummy":
    send_initial_dummy_pkt(eg_port)
elif pkt_type == "courier":
    send_initial_courier_pkt(eg_port)

