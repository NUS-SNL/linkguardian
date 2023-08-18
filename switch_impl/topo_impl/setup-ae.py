import socket
import sys

hostname = socket.gethostname()

RECEIVER_SW_ADDR = 0xAABBCCDDEEFF

if hostname == "p4campus-proc1":
    fp_port_configs = [('5/0', '100G', 'NONE', 2), # lumos ens3f1 
                    ('6/0', '100G', 'NONE', 2), # caelus enp177s0f1 
                    ('1/0', '100G', 'NONE', 0), # loopback link1
                    ('2/0', '100G', 'NONE', 0), # loopback link1
                    ('12/0', '100G', 'NONE', 0), # to sender (tofino1a)
                    ('23/0', '100G', 'NONE', 0), # to receiver (tofino1c)
                    ]
else:
    print("ERROR: Can only run on p4campus-proc1. You are running on {}".format(hostname))
    sys.exit(1)

def add_port_config(port_config):
    speed_dict = {'10G':'BF_SPEED_10G', '25G':'BF_SPEED_25G', '40G':'BF_SPEED_40G','50G':'BF_SPEED_50G', '100G':'BF_SPEED_100G'}
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



port_metadata_tbl = bfrt.topo.pipe.SwitchIngressParser.PORT_METADATA
l2_forward = bfrt.topo.pipe.SwitchIngress.l2_forward
devtest_cmds_file = "/home/sigcomm23ae/linkguardian/switch_impl/topo_impl/devtest_cmds.py"

# For topology figure: https://app.diagrams.net/#G1hy8wHlz500QMTVTgnsO1ZrWA1gGPQ_zx


if hostname == "p4campus-proc1":
    # FORM emulated switches - aka fill the port_metadata table
    port_metadata_tbl.add(ingress_port=128, switch_id=0)
    port_metadata_tbl.add(ingress_port=160, switch_id=0)
    port_metadata_tbl.add(ingress_port=136, switch_id=1)
    port_metadata_tbl.add(ingress_port=36, switch_id=1)
    port_metadata_tbl.add(ingress_port=56, switch_id=2)
    port_metadata_tbl.add(ingress_port=168, switch_id=2)


    # # Add entries to the l2_forward table
    # 100G cx-5 sender side MAC
    l2_forward.add_with_forward(dst_addr=0x1070fdb3618f, switch_id=0, port=160)
    l2_forward.add_with_forward(dst_addr=0x1070fdb3618f, switch_id=1, port=136)
    l2_forward.add_with_forward(dst_addr=0x1070fdb3618f, switch_id=2, port=56)
    
    # 100G cx-5 receiver side MAC
    l2_forward.add_with_forward(dst_addr=0x1070fdb35e6f, switch_id=0, port=128)
    l2_forward.add_with_forward(dst_addr=0x1070fdb35e6f, switch_id=1, port=36)
    l2_forward.add_with_forward(dst_addr=0x1070fdb35e6f, switch_id=2, port=168)

    #  Pktgen pkt's forwarding from sw2 to sw3
    l2_forward.add_with_forward(dst_addr=RECEIVER_SW_ADDR, switch_id=2, port=168)
    

# Setup ARP broadcast for the active dev ports
active_dev_ports = []

if hostname == 'p4campus-proc1':
    active_dev_ports = [160, 168]
else:
    print("This setup script is for p4campus-proc1. But you are running on {}".format(hostname))
    sys.exit(1)

bfrt.pre.node.add(MULTICAST_NODE_ID=0, MULTICAST_RID=0, MULTICAST_LAG_ID=[], DEV_PORT=active_dev_ports)

bfrt.pre.mgid.add(MGID=1, MULTICAST_NODE_ID=[0], MULTICAST_NODE_L1_XID_VALID=[False], MULTICAST_NODE_L1_XID=[0])

# Setup ECN marking for DCTCP
reg_ecn_marking_threshold = bfrt.topo.pipe.SwitchEgress.reg_ecn_marking_threshold
# reg_ecn_marking_threshold.mod(REGISTER_INDEX=0, f1=375) # 375 x 80 = 30KB (20 pkts) | 1 Gbps
reg_ecn_marking_threshold.mod(REGISTER_INDEX=0, f1=1250) # 1250 x 80 = 100KB (65 pkts) | 10 Gbps

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

fp_port_configs_10g = [(port_cfg[0], '10G', port_cfg[2], port_cfg[3]) for port_cfg in fp_port_configs]

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
