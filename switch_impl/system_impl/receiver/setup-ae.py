import socket
import sys
import subprocess
import os
import time


########################
ENABLE_PFC_ON_LOSS_NOTI = False
SEND_PKTGEN_PKTS_TO_EG_AS_PFC = True
ENABLE_PFC_ON_RECIRC_BUFF_THRESH = True

# quanta of 390.625 ==> 2us @100G
# Recovery latency @10G (quanta): min: 97, mean: 121
# Recovery latency @100G (quanta): min: 480, mean: 609
PFC_ON_LOSS_NOTI_QUANTA = 480

# Calculated PFC thresholds (cells)
# 100G: resume = 460, pause = 500
# 25G:  resume = 497, pause = 537
# 10G:  resume = 622, pause = 662
RESUME_THRESHOLD_CELLS = 460  # OLD: 140
PAUSE_THRESHOLD_CELLS = 500  # expected max = 840 (observed 680)@100G # OLD: 180

########################

INTERNAL_RECIRC_PORT_PIPE_0 = 68
RECIRC_PORT_LACK_QID = 1
RECIRC_PORT_RX_BUFFER_QID = 0

COURIER_PKT_QID = 1
LOSS_NOTIFICATION_QID = 2
PAUSE_FRAME_MCAST_RID = 9999
# AFFECTED_FLOWS_REPORTING_DEV_PORT = 132


def generate_mcast_node_id():
    for i in range(1000):
        yield i

curr_mcast_node_id = generate_mcast_node_id()

rx_dev_ports_to_protect = [36]

hostname = socket.gethostname()

linkradar_common_path = ""
python3_scapy_interpreter = ""

if hostname == "tofino1a" or hostname == "tofino1c":
    linkradar_common_path = "/home/sigcomm23ae/linkguardian/switch_impl/system_impl/common"
    python3_scapy_interpreter = "/home/sigcomm23ae/miniconda3/envs/lg/bin/python3"
else:
    print("ERROR: invalid host {}".format(hostname))
    sys.exit(1)


config_pktgen_script='/home/sigcomm23ae/linkguardian/switch_impl/system_impl/receiver/config_pktgen.py'
devtest_cmds_file = "/home/sigcomm23ae/linkguardian/switch_impl/system_impl/receiver/devtest_cmds.py"

init_pkt_injection_script = linkradar_common_path + "/inject_initial_pkt.py"

fp_port_configs = [ ('21/0', '100G', 'NONE', 0), # orig 100G for dev testing
                    ('22/0', '100G', 'NONE', 0),  # FILTER_LPBK_PORT
                    ('23/0', '100G', 'NONE', 0),   # to tofino1b for eval topo
                    ('19/0', '100G', 'NONE', 0), # Recirculation port
                  ]
fp_port_configs_10g = [ ('21/0', '10G', 'NONE', 0), # orig 100G for dev testing
                        ('23/0', '10G', 'NONE', 0),   # to tofino1b for eval topo
                      ]

def add_port_config(port_config):
    speed_dict = {'10G':'BF_SPEED_10G', '25G':'BF_SPEED_25G', '40G':'BF_SPEED_40G', '50G':'BF_SPEED_50G', '100G':'BF_SPEED_100G'}
    fec_dict = {'NONE':'BF_FEC_TYP_NONE', 'FC':'BF_FEC_TYP_FC', 'RS':'BF_FEC_TYP_RS'}
    an_dict = {0:'PM_AN_DEFAULT', 1:'PM_AN_FORCE_ENABLE', 2:'PM_AN_FORCE_DISABLE'}
    lanes_dict = {'10G':(0,1,2,3), '25G':(0,1,2,3), '40G':(0,), '50G':(0,2), '100G':(0,)}
    
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

for config in fp_port_configs:
    add_port_config(config)

# FP port 22/- on tofino1c is dev_port 44. Put it in LPBK mode for filtering.
bfrt.port.port.mod(DEV_PORT=44, LOOPBACK_MODE='BF_LPBK_MAC_NEAR')
# FP port 19/- on tofino1c is dev_port 20. Put it in LPBK mode for recirculation.
bfrt.port.port.mod(DEV_PORT=20, LOOPBACK_MODE='BF_LPBK_MAC_NEAR')


port_metadata_tbl = bfrt.receiver.pipe.SwitchIngressParser.PORT_METADATA

# -----------   OLD when filtering   --------------
port_metadata_tbl.add(ingress_port=36, filter_via_lpbk=1, protect=0, orig_ig_port=36, lpbk_port=44)
port_metadata_tbl.add(ingress_port=44, filter_via_lpbk=0, protect=1, orig_ig_port=36, lpbk_port=44)
#  For timeout pktgen pkts: orig_ig_port is used for lookups
port_metadata_tbl.add(ingress_port=68, filter_via_lpbk=0, protect=0, orig_ig_port=36, lpbk_port=44)
# -------------------------------------------------
# port_metadata_tbl.add(ingress_port=36, filter_via_lpbk=0, protect=1, orig_ig_port=36, lpbk_port=44)

# Add entries to the l2_forward table
l2_forward = bfrt.receiver.pipe.SwitchIngress.l2_forward
l2_forward.add_with_l2_switch(dst_addr=0xAAAABBBBCCCC, port=36) # send to sender switch
l2_forward.add_with_l2_switch(dst_addr=0xAABBCCDDEEFF, port=52) # next-hop eval-topo
l2_forward.add_with_l2_switch(dst_addr=0x1070fdb3618f, port=36) # lumos ens3f1 (via tx)
l2_forward.add_with_l2_switch(dst_addr=0x1070fdb35e6f, port=52) # caelus enp177s0f1 (via 1b)

# Add entries to the leading_ack_max_notify table
leading_ack_max_notify = bfrt.receiver.pipe.SwitchEgress.get_leading_ack_notify_max_count
leading_ack_max_notify.add_with_do_get_leading_ack_notify_max_count(ingress_port=36, count=2)

#####################################
###  LACK UPDATE MIRRORING CONFIG ###
#####################################
MIRROR_SESSION_LACK_UPDATE = 300

bfrt.mirror.cfg.add_with_normal(sid=MIRROR_SESSION_LACK_UPDATE, direction='INGRESS', session_enable=True, ucast_egress_port=INTERNAL_RECIRC_PORT_PIPE_0, ucast_egress_port_valid=1, egress_port_queue = RECIRC_PORT_LACK_QID, max_pkt_len=16)
# The ig_mirror_lack_update_h is 5 bytes only. So can aggressively truncate! 
# But pkt_length gets capped at 20 bytes (as observed in the egress). 4 bytes extra always!

########################################
###  AFFECTED FLOWS MIRRORING CONFIG ###
########################################
# MIRROR_SESSION_AFFECTED_FLOWS = 400

# bfrt.mirror.cfg.add_with_normal(sid=MIRROR_SESSION_AFFECTED_FLOWS, direction='EGRESS', session_enable=True, ucast_egress_port=AFFECTED_FLOWS_REPORTING_DEV_PORT, ucast_egress_port_valid=1, max_pkt_len=16384)

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

for port in rx_dev_ports_to_protect:
    set_q_priority(port, 0, 1)  # normal queue (intermediate priority)
    set_q_priority(port, 1, 0)  # courier/dummy pkt queue (lowest priority)
    set_q_priority(port, 2, 2)  # loss notification queue (highest priority)


##############################################
###  SETTING ROUTING FOR INIT COURIER PKTS ###
##############################################
def route_init_courier_pkt(dev_port, queue_id):
    l2_forward = bfrt.receiver.pipe.SwitchIngress.l2_forward

    dst_mac_addr = (dev_port << 5) | queue_id
    l2_forward.add_with_route_init_courier_pkt(dst_addr=dst_mac_addr, port=dev_port, qid=queue_id)

route_init_courier_pkt(36, COURIER_PKT_QID)

##############################################
###  MIRROR SESSIONS FOR COURIER PKT CLONING
##############################################
RX_MIRROR_SESSIONS_COURIER_PKTS_START=33 # see ReadMe

tbl_courier_pkt_mirror_sessions = bfrt.receiver.pipe.SwitchEgress.get_courier_pkt_mirror_session

curr_session = RX_MIRROR_SESSIONS_COURIER_PKTS_START
for port in rx_dev_ports_to_protect:
    bfrt.mirror.cfg.add_with_normal(sid=curr_session, direction='EGRESS', session_enable=True, ucast_egress_port=port, ucast_egress_port_valid=1, egress_port_queue = COURIER_PKT_QID,  max_pkt_len=16384)

    tbl_courier_pkt_mirror_sessions.add_with_do_get_courier_pkt_mirror_session(egress_port=port, mirror_session=curr_session)

    curr_session += 1


#################################################
###  MIRROR SESSIONS FOR RECIRC BUFF PFC GEN
#################################################
MIRROR_SESSION_EG_PFC = 500

if ENABLE_PFC_ON_RECIRC_BUFF_THRESH:
    bfrt.mirror.cfg.add_with_normal(sid=MIRROR_SESSION_EG_PFC, direction='EGRESS', session_enable=True, ucast_egress_port=rx_dev_ports_to_protect[0], ucast_egress_port_valid=1, egress_port_queue = LOSS_NOTIFICATION_QID, max_pkt_len=21)
    # The eg_mirror_pfc_pkt_h is 3 bytes only + ethernet 14 bytes. So can aggressively truncate! 
    # But pkt_length gets capped at 21 bytes (as observed in the egress). 4 bytes extra always!



##############################################################
###  MIRROR SESSIONS + MCAST GRPS FOR LOSS NOTIFICATION PKTS
##############################################################
RX_MIRROR_SESSIONS_LOSS_NOTIFICATION_PKTS_START = 49 # see ReadMe
RX_MCAST_GRP_ID_LOSS_NOTIFICATION_PKTS_START = 101

tbl_generate_loss_notification = bfrt.receiver.pipe.SwitchIngress.generate_loss_notification

curr_session = RX_MIRROR_SESSIONS_LOSS_NOTIFICATION_PKTS_START
curr_mcast_grp_id = RX_MCAST_GRP_ID_LOSS_NOTIFICATION_PKTS_START

for port in rx_dev_ports_to_protect:
    if ENABLE_PFC_ON_LOSS_NOTI:
        #### Prepare the mcast group ####
        # mcast node for loss notification. rid is set to the devport
        loss_noti_node_id = next(curr_mcast_node_id)
        bfrt.pre.node.add(MULTICAST_NODE_ID=loss_noti_node_id, MULTICAST_RID=port, MULTICAST_LAG_ID=[], DEV_PORT=[port])
        
        # mcast node for PAUSE frame. rid is set to PAUSE_FRAME_MCAST_RID = 9999
        pause_frame_node_id = next(curr_mcast_node_id)
        bfrt.pre.node.add(MULTICAST_NODE_ID=pause_frame_node_id, MULTICAST_RID=PAUSE_FRAME_MCAST_RID, MULTICAST_LAG_ID=[], DEV_PORT=[port])

        # mcast group. NOTE: seq in MULTICAST_NODE_ID array matters.
        # PRE makes the copies in reverse order of the seq specified here
        # in this case loss_noti pkt would be generated *before* pause frame pkt
        bfrt.pre.mgid.add(MGID=curr_mcast_grp_id, MULTICAST_NODE_ID=[pause_frame_node_id, loss_noti_node_id], MULTICAST_NODE_L1_XID_VALID=[False,False], MULTICAST_NODE_L1_XID=[0,0])

        # configure the mirroring session with mcast group
        bfrt.mirror.cfg.add_with_normal(sid=curr_session, direction='INGRESS', session_enable=True, ucast_egress_port=0, ucast_egress_port_valid=0, egress_port_queue = LOSS_NOTIFICATION_QID, mcast_grp_a=curr_mcast_grp_id, mcast_grp_a_valid=1, max_pkt_len=26) # ig_mirror_loss_notification_h (8) + ethernet_hdr (14) = 22 bytes

        # OLD: add table entry for pause quanta
        # tbl_add_pause_quanta = bfrt.receiver.pipe.SwitchEgress.add_pause_quanta
        # tbl_add_pause_quanta.add_with_do_add_pause_quanta(egress_port=36, pause_quanta=0xffff)

        # add table entry for PFC quanta
        tbl_add_pfc_c1_quanta = bfrt.receiver.pipe.SwitchEgress.add_pfc_c1_quanta
        # quanta of 390.625 ==> 2us @100G | Recovery latency @10G: min: 97, mean: 121
        tbl_add_pfc_c1_quanta.add_with_do_add_pfc_c1_quanta(egress_port=36, c1_quanta=PFC_ON_LOSS_NOTI_QUANTA)

        curr_mcast_grp_id += 1

    else: # configure normal mirroring session w/o PAUSE frames
        bfrt.mirror.cfg.add_with_normal(sid=curr_session, direction='INGRESS', session_enable=True, ucast_egress_port=port, ucast_egress_port_valid=1, egress_port_queue = LOSS_NOTIFICATION_QID, max_pkt_len=26) # ig_mirror_loss_notification_h (8) + ethernet_hdr (14) = 22 bytes
    
    # add table entry for mirroring
    tbl_generate_loss_notification.add_with_do_generate_loss_notification(orig_ig_port=port, mirror_session=curr_session)
    curr_session += 1

#####################################
###  PFC FRAMES ON TIMEOUT EVENTS ###
#####################################
tbl_add_pfc_hdr_and_route = bfrt.receiver.pipe.SwitchIngress.add_pfc_hdr_and_route

def enable_pfc_on_pktgen(): # actual:3906.25 => 20us @100G
    tbl_add_pfc_hdr_and_route.set_default_with_do_add_pfc_hdr_and_route(egress_port=36)
def disable_pfc_on_pktgen():
    tbl_add_pfc_hdr_and_route.set_default_with_drop()

if SEND_PKTGEN_PKTS_TO_EG_AS_PFC:
    enable_pfc_on_pktgen()




#######################################
###  INJECTING INITIAL COURIER PKTS ###
#######################################
print("######## INITIAL COURIER PKT(S) INJECTION ########")
output = subprocess.check_output(['sudo', python3_scapy_interpreter, init_pkt_injection_script, 'courier', '36'])
print(output.decode("utf-8"))


###############################################
###  CONFIG PKTGEN + START ACK TIMEOUT PKTS ###
###############################################
print("######## CONFIGURING PKTGEN ########")
os.system("$SDE/run_pd_rpc.py {}".format(config_pktgen_script))
time.sleep(0.5)
bfrt.tf1.pktgen.app_cfg.mod_with_trigger_timer_periodic(app_id=1, app_enable=True)
print("ACK timeout traffic started!")


###############################
###  LOAD DEVTEST_CMDS FILE ###
###############################
print("######## LOADING DEVTEST COMMANDS ########")
with open(devtest_cmds_file, "rb") as src_file:
    code = compile(src_file.read(), devtest_cmds_file, "exec")
exec(code)
print("devtest_cmds.py loaded!")

##############################
# Setup ECN marking for DCTCP
##############################
# reg_ecn_marking_threshold = bfrt.receiver.pipe.SwitchEgress.reg_ecn_marking_threshold
# reg_ecn_marking_threshold.mod(REGISTER_INDEX=0, f1=375) # 375 x 80 = 30KB (20 pkts) | 1 Gbps
# reg_ecn_marking_threshold.mod(REGISTER_INDEX=0, f1=1250) # 1250 x 80 = 100KB (65 pkts) | 10 Gbps

#######################################
# Setup Recirc Buffer PFC thresholds
#######################################
reg_recirc_buffer_pfc_pause_threshold = bfrt.receiver.pipe.SwitchEgress.reg_recirc_buffer_pfc_pause_threshold
reg_recirc_buffer_pfc_pause_threshold.mod(REGISTER_INDEX=0, f1=PAUSE_THRESHOLD_CELLS) 
# OLD pause thresh 93: 93 x 80 = 7440B (~6us @10G)

reg_recirc_buffer_pfc_resume_threshold = bfrt.receiver.pipe.SwitchEgress.reg_recirc_buffer_pfc_resume_threshold
reg_recirc_buffer_pfc_resume_threshold.mod(REGISTER_INDEX=0, f1=RESUME_THRESHOLD_CELLS)


################################
# AE Setup Extras/Overrides
################################

enable_protection_script = "/home/sigcomm23ae/linkguardian/switch_impl/system_impl/receiver/enable_protection_on_tx.py"
rx_counters_poll_grpc_script="/home/sigcomm23ae/linkguardian/switch_impl/expt_scripts/effective_lossRate_linkSpeed/poll_rx_counters.py"

devports_to_check = {20:"rx_recirc_buff", 
                     36:"protected_link_rx",
                     44:"rx_filtering_port", 
                     52: "large_topo_p4campus-proc1_conn"
                    }

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
