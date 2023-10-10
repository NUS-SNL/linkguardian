import socket
import sys
import subprocess
import os
import time
import math

tx_dev_ports_to_protect = [32] #[52]
TX_PROTECTED_DEV_PORT = 32

RECIRC_PORT_PIPE_0 = 68
RECIRC_BUFFERING_Q_ID = 0
DUMMY_PKT_QID = 1
RETX_QID = 2
AFFECTED_FLOWS_REPORTING_DEV_PORT = 60

NUM_RETX_COPIES = 2

# Setup RED-based ECN marking for DCQCN
DCQCN_K_MIN = 1250 # 100KB
DCQCN_K_MAX = 3000 # 240KB  # 400KB - 5000
DCQCN_P_MAX = 0.2 # 20%
QDEPTH_RANGE_MAX = 2**19
SEED_RANGE_MAX = 256 # random number range ~ [0, 255] (8bits)


hostname = socket.gethostname()

linkradar_common_path = ""
python3_scapy_interpreter = ""

if hostname == "tofino1a" or hostname == "tofino1c":
    linkradar_common_path = "/home/sigcomm23ae/linkguardian/switch_impl/system_impl/common"
    python3_scapy_interpreter = "/home/sigcomm23ae/miniconda3/envs/lg/bin/python3"
else:
    print("ERROR: invalid host {}".format(hostname))
    sys.exit(1)

config_pktgen_script='/home/sigcomm23ae/linkguardian/switch_impl/system_impl/sender/config_pktgen.py'
devtest_cmds_file = "/home/sigcomm23ae/linkguardian/switch_impl/system_impl/sender/devtest_cmds.py"


init_pkt_injection_script = linkradar_common_path + "/inject_initial_pkt.py"

fp_port_configs = [('21/0', '10G', 'NONE', 0), # orig 100G for dev testing
                   ('12/0', '10G', 'NONE', 0), # to tofino1b for eval topo
                   ('19/0', '100G', 'NONE', 0)  # Recirculation port
                  ]
fp_port_configs_10g = [('21/0', '10G', 'NONE', 0), # orig 100G for dev testing
                       ('12/0', '10G', 'NONE', 0), # to tofino1b for eval topo 
                      ] # for easy change of link speeds

speed_dict = {'10G':'BF_SPEED_10G', '25G':'BF_SPEED_25G', '40G':'BF_SPEED_40G', '50G':'BF_SPEED_50G', '100G':'BF_SPEED_100G'}
fec_dict = {'NONE':'BF_FEC_TYP_NONE', 'FC':'BF_FEC_TYP_FC', 'RS':'BF_FEC_TYP_RS'}
an_dict = {0:'PM_AN_DEFAULT', 1:'PM_AN_FORCE_ENABLE', 2:'PM_AN_FORCE_DISABLE'}
lanes_dict = {'10G':(0,1,2,3), '25G':(0,1,2,3), '40G':(0,), '50G':(0,2), '100G':(0,)}

def add_port_config(port_config):
    # extract and map values from the config first
    conf_port = int(port_config[0].split('/')[0])
    lane = port_config[0].split('/')[1]
    conf_speed = speed_dict[port_config[1]]
    conf_fec = fec_dict[port_config[2]]
    conf_an = an_dict[port_config[3]]


    if lane == '-': # need to add all possible lanes
        lanes = lanes_dict[port_config[1]]
        for lane in lanes:
            dp = bfrt.port.port_hdl_info.get(CONN_ID=conf_port, CHNL_ID=lane, print_ents=False).data[b'$DEV_PORT']
            bfrt.port.port.add(DEV_PORT=dp, SPEED=conf_speed, FEC=conf_fec, AUTO_NEGOTIATION=conf_an, PORT_ENABLE=True)
    else: # specific lane is requested
        conf_lane = int(lane)
        dp = bfrt.port.port_hdl_info.get(CONN_ID=conf_port, CHNL_ID=conf_lane, print_ents=False).data[b'$DEV_PORT']
        bfrt.port.port.add(DEV_PORT=dp, SPEED=conf_speed, FEC=conf_fec, AUTO_NEGOTIATION=conf_an, PORT_ENABLE=True)

def modify_port_config(port_config):
    conf_port = int(port_config[0].split('/')[0])
    lane = port_config[0].split('/')[1]

    # first: delete the devport/devports
    if lane == '-': # need to delete all possible lanes
        lanes = lanes_dict[port_config[1]]
        for lane in lanes:
            dp = bfrt.port.port_hdl_info.get(CONN_ID=conf_port, CHNL_ID=lane, print_ents=False).data[b'$DEV_PORT']
            bfrt.port.port.delete(DEV_PORT=dp)
    else: # specific lane is requested
        conf_lane = int(lane)
        dp = bfrt.port.port_hdl_info.get(CONN_ID=conf_port, CHNL_ID=conf_lane, print_ents=False).data[b'$DEV_PORT']
        bfrt.port.port.delete(DEV_PORT=dp)

    # now add the new config
    add_port_config(port_config)


def get_pg_id(dev_port):
    # each pipe has 128 dev_ports + divide by 4 to get the pg_id
    pg_id = (dev_port % 128) >> 2 
    return pg_id

def get_pg_queue(dev_port, qid):
    lane = dev_port % 4
    pg_queue = lane * 8 + qid # there are 8 queues per lane
    return pg_queue


for config in fp_port_configs:
    add_port_config(config)

# FP port 19/- on tofino1a is dev_port 16. Put it in LPBK mode for recirc.
bfrt.port.port.mod(DEV_PORT=16, LOOPBACK_MODE='BF_LPBK_MAC_NEAR')


# Add entries to the l2_forward table
l2_forward = bfrt.sender.pipe.SwitchIngress.l2_forward
l2_forward.add_with_forward(dst_addr=0xAABBCCDDEEFF, port=32) # trafficGen traffic
l2_forward.add_with_forward(dst_addr=0x1070fdb3618f, port=36) # lumos ens3f1 (via 1b) 
l2_forward.add_with_forward(dst_addr=0x1070fdb35e6f, port=32) # caelus enp177s0f1 (via rx)

link_protect = bfrt.sender.pipe.SwitchEgress.link_protect
# link_protect.add_with_protect(egress_port=32, dummy_pkt_max_count=3)

########################################
###  AFFECTED FLOWS MIRRORING CONFIG ###
########################################
MIRROR_SESSION_AFFECTED_FLOWS = 400

bfrt.mirror.cfg.add_with_normal(sid=MIRROR_SESSION_AFFECTED_FLOWS, direction='EGRESS', session_enable=True, ucast_egress_port=AFFECTED_FLOWS_REPORTING_DEV_PORT, ucast_egress_port_valid=1, max_pkt_len=16384)

#################################
###  SETTING QUEUE PRIORITIES ###
#################################

def set_q_priority(dev_port, qid, priority):
    q_sched_cfg = bfrt.tf1.tm.queue.sched_cfg

    # Source for following formulae: https://community.intel.com/t5/Intel-Connectivity-Research/Ask-about-the-implementation-of-Strict-Priority-in-Tofino/m-p/1329327#M2767
    
    pipe_id = dev_port >> 7
    portgrp_id = (dev_port % 128) >> 2  # each pipe has 128 dev_ports + divide by 4 to get the pg_id
    lane = dev_port % 4
    portgrp_queue = lane * 8 + qid # there are 8 queues per lane

    q_sched_cfg.mod(pipe=pipe_id, pg_id=portgrp_id, pg_queue=portgrp_queue, max_priority = priority)

for port in tx_dev_ports_to_protect:
    set_q_priority(port, 0, 1)  # normal queue (intermediate priority)
    set_q_priority(port, 1, 0)  # courier/dummy pkt queue (lowest priority)
    set_q_priority(port, 2, 2)  # loss notification/reTx queue (highest priority)

##############################################
###  SETTING ROUTING FOR INIT DUMMY PKTS ###
##############################################
def route_init_dummy_pkt(dev_port, queue_id):
    l2_forward = bfrt.sender.pipe.SwitchIngress.l2_forward

    dst_mac_addr = (dev_port << 5) | queue_id
    l2_forward.add_with_route_init_dummy_pkt(dst_addr=dst_mac_addr, port=dev_port, qid=queue_id)

route_init_dummy_pkt(32, DUMMY_PKT_QID)

#################################################
###  MIRROR SESSIONS FOR BUFFERED PKTS
#################################################
TX_MIRROR_SESSIONS_BUFFERED_PKTS_START = 1 # see ReadMe

copy_pkt_for_buffering = bfrt.sender.pipe.SwitchEgress.copy_pkt_for_buffering

curr_session = TX_MIRROR_SESSIONS_BUFFERED_PKTS_START

for port in tx_dev_ports_to_protect:
    # TODO: currently all buffered pkts go to the same recirc port
    bfrt.mirror.cfg.add_with_normal(sid=curr_session, direction='EGRESS', session_enable=True, ucast_egress_port=RECIRC_PORT_PIPE_0, ucast_egress_port_valid=1, egress_port_queue = RECIRC_BUFFERING_Q_ID, max_pkt_len=16384)
    copy_pkt_for_buffering.add_with_copy_for_buffering(egress_port=port, mirror_session=curr_session)
    curr_session += 1


#################################################
###  MIRROR SESSIONS FOR DUMMY PKTS
#################################################
TX_MIRROR_SESSIONS_DUMMY_PKTS_START = 17 # see ReadMe

mirror_dummy_pkt = bfrt.sender.pipe.SwitchEgress.mirror_dummy_pkt

curr_session = TX_MIRROR_SESSIONS_DUMMY_PKTS_START

for port in tx_dev_ports_to_protect:
    # TODO: currently all buffered pkts go to the same recirc port
    bfrt.mirror.cfg.add_with_normal(sid=curr_session, direction='EGRESS', session_enable=True, ucast_egress_port=port, ucast_egress_port_valid=1, egress_port_queue = DUMMY_PKT_QID, max_pkt_len=16384)
    mirror_dummy_pkt.add_with_do_mirror_dummy_pkt(egress_port=port, mirror_session=curr_session)
    curr_session += 1


#####################################
###  INJECTING INITIAL DUMMY PKTS ###
#####################################
print("######## INITIAL DUMMY PKT(S) INJECTION ########")
output = subprocess.check_output(['sudo', python3_scapy_interpreter, init_pkt_injection_script, 'dummy', '32'])
print(output.decode("utf-8"))


##################################
# Multicast Setup funcs for ReTx
##################################
TX_MULTICAST_GRPS_BUFFERED_PKTS_START = 1 # see ReadMe
tbl_retx_mcast_buffered_pkt = bfrt.sender.pipe.SwitchIngress.retx_mcast_buffered_pkt

def get_number_of_retx_copies(devport=TX_PROTECTED_DEV_PORT):
    entry = tbl_retx_mcast_buffered_pkt.get(dst_eg_port=devport, print_ents=False)
    if entry == -1:
        print("No entry for dst port {} in the table retx_mcast_buffered_pkt".format(devport))
        return 0
    if entry.action == 'SwitchIngress.do_retx_buffered_pkt_ucast':
        return 1
    elif entry.action == 'SwitchIngress.do_retx_buffered_pkt_mcast':
        mgid = entry.data[b'grp_id']
        mgid_entry = bfrt.pre.mgid.get(MGID=mgid, print_ents=False)
        num_retx_copies = len(mgid_entry.data[b'$MULTICAST_NODE_ID'])
        return num_retx_copies
    else:
        print("Unknown action for dst port {}: {}".format(devport, entry.action))

def clear_retx_mcast_pre_tables(mgid):
    mgid_entry = bfrt.pre.mgid.get(MGID=mgid, print_ents=False)
    nodes = mgid_entry.data[b'$MULTICAST_NODE_ID']
    # delete the nodes
    for node in nodes:
         bfrt.pre.node.delete(MULTICAST_NODE_ID=node)
    # delete the mgid entry
    bfrt.pre.mgid.delete(MGID=mgid)

# TODO: Only handles a *single* corrupting port scenario for now using 
# TX_MULTICAST_GRPS_BUFFERED_PKTS_START
def set_number_of_retx_copies(num_retx_copies, devport=TX_PROTECTED_DEV_PORT):
    curr_num_retx_copies = get_number_of_retx_copies(devport)
    if num_retx_copies == curr_num_retx_copies:
        print("Number of retx copies for dst port {} already set to {}".format(devport, num_retx_copies))
        return
    
    # clear the entry from the table
    try:
        tbl_retx_mcast_buffered_pkt.delete(dst_eg_port=devport)
    except: #  BfRtTableError:
        pass

    if curr_num_retx_copies > 1: # clear pre node and mgid tables
        clear_retx_mcast_pre_tables(TX_MULTICAST_GRPS_BUFFERED_PKTS_START)
    
    if num_retx_copies == 0:
        pass # we hv already cleared the table above
    elif num_retx_copies == 1:
        tbl_retx_mcast_buffered_pkt.add_with_do_retx_buffered_pkt_ucast(dst_eg_port=devport)
    else: 
        # add pre nodes first
        nodes = []
        nodes_xid_valid = []
        nodes_l1_xid = []
        for i in range(num_retx_copies):
            bfrt.pre.node.add(MULTICAST_NODE_ID=i, MULTICAST_RID=i, MULTICAST_LAG_ID=[], DEV_PORT=[devport])
            nodes.append(i)
            nodes_xid_valid.append(False)
            nodes_l1_xid.append(0)
        # add pre mgid now
        bfrt.pre.mgid.add(MGID=TX_MULTICAST_GRPS_BUFFERED_PKTS_START, MULTICAST_NODE_ID=nodes, MULTICAST_NODE_L1_XID_VALID=nodes_xid_valid, MULTICAST_NODE_L1_XID=nodes_l1_xid)
        
        # add entry to the mcast decision table
        tbl_retx_mcast_buffered_pkt.add_with_do_retx_buffered_pkt_mcast(dst_eg_port=devport, grp_id=TX_MULTICAST_GRPS_BUFFERED_PKTS_START)


#################################################
###  SETTING UCAST/MCAST SESSIONS FOR RETX
#################################################
set_number_of_retx_copies(NUM_RETX_COPIES, TX_PROTECTED_DEV_PORT)


##############################
# Setup ECN marking for DCTCP
##############################
reg_ecn_marking_threshold = bfrt.sender.pipe.SwitchEgress.reg_ecn_marking_threshold
# reg_ecn_marking_threshold.mod(REGISTER_INDEX=0, f1=375) # 375 x 80 = 30KB (20 pkts) | 1 Gbps
reg_ecn_marking_threshold.mod(REGISTER_INDEX=0, f1=1250) # 1250 x 80 = 100KB (65 pkts) | 10 Gbps


#######################
###  CONFIG PKTGEN  ### 
#######################
print("######## CONFIGURING PKTGEN ########")
os.system("$SDE/run_pd_rpc.py {}".format(config_pktgen_script))
time.sleep(0.5)
print("PktGen configured for test traffic!")


#################################
###  DCQCN ECN MARKING CONFIG ###
#################################

SEED_K_MAX = math.ceil(DCQCN_P_MAX * SEED_RANGE_MAX) # 52
QDEPTH_STEPSIZE = math.floor((DCQCN_K_MAX - DCQCN_K_MIN) / SEED_K_MAX) # 72

last_range = DCQCN_K_MIN
#####################
# PROBABILITY TABLE #
#####################
dcqcn_get_ecn_probability = bfrt.sender.pipe.SwitchEgress.dcqcn_get_ecn_probability
# < K_MIN
# print("DCQCN Table -- Adding qdepth:[{}, {}] -> probability:{:.2f}% ({}/{})".format(0, DCQCN_K_MIN - 1, float(0/SEED_RANGE_MAX)*100, 0, SEED_RANGE_MAX))
dcqcn_get_ecn_probability.add_with_dcqcn_mark_probability(deq_qdepth_start=0, deq_qdepth_end=DCQCN_K_MIN - 1, value=0)
# K_MIN < qDepth < K_MAX
for i in range(1, SEED_K_MAX):
    # print("DCQCN Table -- Adding qdepth:[{}, {}] -> probability:{:.2f}% ({}/{})".format(last_range, last_range + QDEPTH_STEPSIZE - 1, float(i/SEED_RANGE_MAX)*100, i, SEED_RANGE_MAX))
    dcqcn_get_ecn_probability.add_with_dcqcn_mark_probability(deq_qdepth_start=last_range, deq_qdepth_end=last_range + QDEPTH_STEPSIZE - 1, value=i)
    last_range += QDEPTH_STEPSIZE
# > K_MAX
# print("DCQCN Table -- Adding qdepth:[{}, {}] -> probability:{:.2f}%".format(last_range, QDEPTH_RANGE_MAX - 1, float(SEED_RANGE_MAX/SEED_RANGE_MAX)*100))
dcqcn_get_ecn_probability.add_with_dcqcn_mark_probability(deq_qdepth_start=last_range, deq_qdepth_end=QDEPTH_RANGE_MAX - 1, value=SEED_RANGE_MAX - 1)

####################
# COMPARISON TABLE #
####################
dcqcn_compare_probability = bfrt.sender.pipe.SwitchEgress.dcqcn_compare_probability
# Less than 100%
for prob_output in range(1, SEED_K_MAX): 
    for random_number in range(SEED_RANGE_MAX): # 0 ~ 255
        if random_number < prob_output:
            # print("Comparison Table -- ECN Marking for Random Number {}, Output Value {}".format(random_number, prob_output))
            bfrt.sender.pipe.SwitchEgress.dcqcn_compare_probability.add_with_dcqcn_check_ecn_marking(dcqcn_prob_output=prob_output, dcqcn_random_number=random_number)
# 100% ECN Marking
for random_number in range(SEED_RANGE_MAX):
    prob_output = SEED_RANGE_MAX - 1
    # print("Comparison Table -- ECN Marking for Random Number {} < Output Value {}".format(random_number, prob_output))
    bfrt.sender.pipe.SwitchEgress.dcqcn_compare_probability.add_with_dcqcn_check_ecn_marking(dcqcn_prob_output=prob_output, dcqcn_random_number=random_number)

print("DCQCN ECN marking configured!")


###############################
###  LOAD DEVTEST_CMDS FILE ###
###############################
print("######## LOADING DEVTEST COMMANDS ########")
with open(devtest_cmds_file, "rb") as src_file:
    code = compile(src_file.read(), devtest_cmds_file, "exec")
exec(code)
print("devtest_cmds.py loaded!")


################################
# AE Setup Extras/Overrides
################################

### AE Path Overrides ###
TX_BUFFER_DATA_DUMP_PATH = '/home/sigcomm23ae/traces/effective_lossRate_linkSpeed'
rx_ok_counter_script = '/home/sigcomm23ae/linkguardian/switch_impl/system_impl/sender/get_rx_ok_counter.py'
rx_forwarded_counter_script = '/home/sigcomm23ae/linkguardian/switch_impl/expt_scripts/effective_lossRate_linkSpeed/get_rx_forwarded_counter.py'

devports_to_check = {16:"tx_recirc_buff", 
                     32:"protected_link_tx", 
                     36:"large_topo_p4campus-proc1_conn"
                    }


ssh_alias_rx_switch = "tofino1c-ae"
ssh_alias_topo_switch = "p4campus-proc1-ae"
sde_install_on_rx = '/home/sigcomm23ae/bf-sde-9.9.0/install'
poll_rx_counters_script_on_rx = '/home/sigcomm23ae/linkguardian/switch_impl/expt_scripts/effective_lossRate_linkSpeed/poll_rx_counters.py'


def change_link_speeds(new_link_speed):
    if new_link_speed == 10:
        for port_cfg in fp_port_configs_10g:
            modify_port_config(port_cfg)
    elif new_link_speed == 25:
        for port_cfg in fp_port_configs_10g:
            port_cfg_25g = (port_cfg[0], '25G', port_cfg[2], port_cfg[3])
            modify_port_config(port_cfg_25g)
    elif new_link_speed == 100:
        for port_cfg in fp_port_configs_10g:
            port_cfg_100g = (port_cfg[0], '100G', port_cfg[2], port_cfg[3])
            modify_port_config(port_cfg_100g)
    else:
        print("ERROR: Invalid link speed {}".format(new_link_speed))
        return
