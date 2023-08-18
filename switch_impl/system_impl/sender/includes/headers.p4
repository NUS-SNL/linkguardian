#ifndef _HEADERS_
#define _HEADERS_

#include "../../common/linkradar_hdr.p4"

typedef bit<48> mac_addr_t;
typedef bit<32> ipv4_addr_t;
typedef bit<4> internal_hdr_type_t;
typedef bit<4> internal_hdr_info_t;

const internal_hdr_type_t INTERNAL_HDR_TYPE_BRIDGED_META = 0xA;
const internal_hdr_type_t INTERNAL_HDR_TYPE_IG_MIRROR = 0xB;
const internal_hdr_type_t INTERNAL_HDR_TYPE_EG_MIRROR = 0xC;
const internal_hdr_type_t INTERNAL_HDR_TYPE_EG_MIRROR_AFFECTED_FLOW = 0xD;

/* Egress Mirror Types */
const bit<3> EG_MIRROR_BUFFERED_PKT  = 1;
const bit<3> EG_MIRROR_DUMMY_PKT  = 2;
const bit<3> EG_MIRROR_AFFECTED_FLOW = 3; // for deparser to emit common hdr

/* EG_MIRROR_AFFECTED_FLOW subtypes */
const bit<4> EG_MIRROR_AFFECTED_FLOW_UNPROTECTED = 0;
const bit<4> EG_MIRROR_AFFECTED_FLOW_PROTECTED = 1;

/* Mirror Sessions */
const int MIRROR_SESSION_BUFFERING = 700;
const int MIRROR_SESSION_AFFECTED_FLOWS = 400;

#define INTERNAL_HEADER           \
    internal_hdr_type_t type; \
    internal_hdr_info_t info

header internal_hdr_h {
    INTERNAL_HEADER;
}

/* Any metadata to be bridged from ig to eg */
header bridged_meta_h {
    INTERNAL_HEADER;
    /* Add any metadata to be bridged from ig to eg */
}

header eg_mirror_buffered_pkt_h {
    INTERNAL_HEADER;
    @padding bit<6> _pad;
    bit<1> emulated_dropped;
    PortId_t dst_eg_port; // 9 bits
    // NOTE: could be simply 8 bits. But ran into internal compiler error with SDE 9.7.0
}

header eg_mirror_dummy_pkt_h {
    INTERNAL_HEADER;
}

header eg_mirror_affected_flow_h {
    INTERNAL_HEADER;
    // bit<8> hole_size;
}



header ethernet_h {
	mac_addr_t dst_addr;
	mac_addr_t src_addr;
	bit<16> ether_type;
}

header remaining_ethernet_h {
	mac_addr_t src_addr;
	bit<16> ether_type;
}

header arp_h {
    bit<16> htype;
    bit<16> ptype;
    bit<8> hlen;
    bit<8> plen;
    bit<16> oper;
    mac_addr_t sender_hw_addr;
    ipv4_addr_t sender_ip_addr;
    mac_addr_t target_hw_addr;
    ipv4_addr_t target_ip_addr;
}

header ipv4_h {
	bit<4> version;
    bit<4> ihl;
    bit<6> dscp;
    bit<2> ecn;
    bit<16> total_len;
    bit<16> identification;
    bit<3> flags;
    bit<13> frag_offset;
    bit<8> ttl;
    bit<8> protocol;
    bit<16> hdr_checksum;
    ipv4_addr_t src_addr;
    ipv4_addr_t dst_addr;
}

header tcp_h {
    bit<16> src_port;
    bit<16> dst_port;
    bit<32> seq_no;
    bit<32> ack_no;
    bit<4> data_offset;
    bit<4> res;
    bit<8> flags;
    bit<16> window;
    bit<16> checksum;
    bit<16> urgent_ptr;
}

header udp_h {
    bit<16> src_port;
    bit<16> dst_port;
    bit<16> hdr_length;
    bit<16> checksum;
}

struct lack_hole_records_t {
    seq_no_t lack;
    seq_no_t first_lost_seq_no;
}

struct buffered_dropped_record_t {
    seq_no_t curr_lack;
    seq_no_t buffered_seq_no;
}

struct header_t {
    bridged_meta_h bridged_meta; // deparsed from ig to eg
    pktgen_timer_header_t pktgen_timer;
    remaining_ethernet_h remaining_ethernet;
	ethernet_h ethernet;
    linkradar_buffered_h linkradar_buffered; // IMP: ordering between lr_buffered and lr_data 
    linkradar_data_h linkradar_data;
    linkradar_lack_h linkradar_lack; // IMP: ordering between lack and loss_notification
    linkradar_loss_notification_h linkradar_loss_notification;
	ipv4_h ipv4;
    arp_h arp;
	tcp_h tcp;
	udp_h udp;
}

struct ig_metadata_t {
    bit<17> holes_1_idx; // needed for multi-hole update table
    
    // Used for checking if buffered pkt is a missing hole
    bit<1> is_missing_hole_1;
    bit<1> is_missing_hole_2;
    bit<1> is_missing_hole_3;
    bit<1> is_missing_hole_4;
    bit<1> is_missing_hole_5;

    // used for setting multiple holes
    seq_no_t holes_2_seq_no;
    seq_no_t holes_3_seq_no;
    seq_no_t holes_4_seq_no;
    seq_no_t holes_5_seq_no;
    seq_no_t first_lost_seq_no_copy;

    seq_no_t curr_leading_ack;
    bit<8> curr_era;
    seq_no_t buffered_seq_no;
    seq_no_t min_val;
    bit<1> retx; 

    bit<32> lack_hole_records_idx;
    bit<32> buffered_dropped_records_idx;
}

struct eg_metadata_t {
    internal_hdr_type_t internal_hdr_type;
    internal_hdr_info_t internal_hdr_info;
    MirrorId_t mirror_session;

    bridged_meta_h bridged_meta;
    eg_mirror_buffered_pkt_h eg_mirror_buffered_pkt;
    eg_mirror_dummy_pkt_h eg_mirror_dummy_pkt;
    eg_mirror_affected_flow_h eg_mirror_affected_flow;

    seq_no_t corruption_seq_no;
    bit<1> emulate_corruption;

    bit<1> is_dummy_pkt_pending;
    bit<8> dummy_pkt_notify_max_count;

    bit<1> emulated_dropped;
    PortId_t dst_eg_port;

    bit<1> mark_ecn_codepoint;
    bit<1> is_roce_v2;
    bit<8> dcqcn_prob_output;
    bit<8> dcqcn_random_number; 
}

#endif
