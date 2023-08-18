#ifndef _HEADERS_
#define _HEADERS_

#include "../../common/linkradar_hdr.p4"

#define RANDOM_GEN_BIT_WIDTH 20
#define RANDOM_DROP_TABLE_SIZE 128000 // 2^20 * 0.12 = 125829.12

enum bit<8> pfc_state_t {
    RESUMED = 0,
    PAUSED = 1
}

typedef bit<48> mac_addr_t;
typedef bit<32> ipv4_addr_t;
typedef bit<4> internal_hdr_type_t;
typedef bit<4> internal_hdr_info_t;
typedef bit<RANDOM_GEN_BIT_WIDTH> random_gen_bitwidth_t;

const internal_hdr_type_t INTERNAL_HDR_TYPE_BRIDGED_META = 0xA;
const internal_hdr_type_t INTERNAL_HDR_TYPE_IG_MIRROR = 0xB;
const internal_hdr_type_t INTERNAL_HDR_TYPE_EG_MIRROR = 0xC;

/* Ingress Mirror Types */
// const bit<3> IG_MIRROR_AFFECTED_FLOW = 3w1;
const bit<3> IG_MIRROR_LACK_UPDATE  = 3w2;
const bit<3> IG_MIRROR_LOSS_NOTIFICATION = 3w3;

/* Egress Mirror Types */
const bit<3> EG_MIRROR_COURIER_PKT  = 1;
const bit<3> EG_MIRROR_PFC_PKT      = 2;
// const bit<3> EG_MIRROR_AFFECTED_FLOW  = 3;

/* Mirror Sessions */
const int MIRROR_SESSION_LACK_UPDATE = 300;
const int MIRROR_SESSION_LOSS_NOTIFICATION = 500;
// const int MIRROR_SESSION_AFFECTED_FLOWS = 400;


#define INTERNAL_HEADER           \
    internal_hdr_type_t type; \
    internal_hdr_info_t info

header internal_hdr_h {
    INTERNAL_HEADER;
}

/* Any metadata to be bridged from ig to eg */
header bridged_meta_h {
    INTERNAL_HEADER;
    // @padding bit<7> _pad;
    // bit<1> affected_flow;
    // Add more metadata to be bridged from ig to eg
}

// header eg_mirror_affected_flow_h {
//     INTERNAL_HEADER;
//     // bit<8> hole_size;
// }

header ig_mirror_lack_update_h { // 5 bytes
    INTERNAL_HEADER;
    bit<8> ingress_port;
    bit<16> leading_ack;
    @padding bit<7> _pad; 
    bit<1> leading_ack_era;
}

header ig_mirror_loss_notification_h { // 8 bytes
    INTERNAL_HEADER;
    seq_no_t hole_size; 
    seq_no_t first_lost_seq_no;
    seq_no_t leading_ack;
    @padding bit<7> _pad;
    bit<1> leading_ack_era;
    // bit<1> from_dummy_pkt;
}

header eg_mirror_courier_pkt_h {
    INTERNAL_HEADER;
}

header eg_mirror_pfc_pkt_h { // 3 bytes
    INTERNAL_HEADER;
    bit<16> pfc_quanta;
}


struct port_metadata_t { // max: 64 bits
    bit<1> filter_via_lpbk;
    bit<1> protect;
    PortId_t orig_ig_port; // 9 bits
    PortId_t lpbk_port; // 9 bits
};

struct pkt_record_t {
	bit<16> seq_no;  // seq_no
	bit<16> ts;  // timestamp
}

struct pkt_ipg_record_t {
	bit<32> prev_ts;
	bit<32> curr_ts;
}

struct qdepth_record_t {
	bit<32> time;
	bit<32> qdepth;
}

struct ack_record_t {
    bit<16> ack_no;
    bit<16> time_remaining;
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

header tcp_payload_t {
    bit<8> payload_byte;
}

header resubmit_h { // 8 bytes
    bit<32> ig_ts_t1;
    bit<32> _pad0;
}

header ether_pause_h {
    bit<16> op_code;
    bit<16> pause_quanta;
}

header ether_pfc_h {
    bit<16> op_code;
    bit<8> _reserved;
    
    // enabled bits (8 in total)
    bit<1> c7_enabled; 
    bit<1> c6_enabled; 
    bit<1> c5_enabled; 
    bit<1> c4_enabled; 
    bit<1> c3_enabled; 
    bit<1> c2_enabled; 
    bit<1> c1_enabled; 
    bit<1> c0_enabled;

    bit<16> c0_quanta;
    bit<16> c1_quanta;
    bit<16> c2_quanta;
    bit<16> c3_quanta;
    bit<16> c4_quanta;
    bit<16> c5_quanta;
    bit<16> c6_quanta;
    bit<16> c7_quanta;
}

struct header_t {
    bridged_meta_h bridged_meta; // deparsed from ig to eg
    pktgen_timer_header_t pktgen_timer;
    remaining_ethernet_h remaining_ethernet;
	ethernet_h ethernet;
    ether_pause_h ether_pause;
    ether_pfc_h ether_pfc;
    arp_h arp;
    linkradar_data_h linkradar_data; // IMP ordering: lr_data --> lr_rx_buffered
    linkradar_rx_buffered_h linkradar_rx_buffered; 
    linkradar_lack_h linkradar_lack;
    linkradar_loss_notification_h linkradar_loss_notification;
	ipv4_h ipv4;
	tcp_h tcp;
	udp_h udp;
}

struct ig_metadata_t {
    port_metadata_t port_md;

    bit<32> pkt_record_idx;
    pkt_record_t pkt_record;

    bit<32> pkt_ipg_record_idx;
    pkt_ipg_record_t pkt_ipg_record;
    bit<32> prev_ts;
    bit<32> time_diff;
    bit<32> min_val_ipg;

    MirrorId_t mirror_session; 
    internal_hdr_type_t internal_hdr_type; 
    internal_hdr_info_t internal_hdr_info; 

    bit<8> ingress_port;
    seq_no_t leading_ack;
    bit<1> leading_ack_era;
    bit<1> from_dummy_pkt;

    seq_no_t expected_seq_no;
    seq_no_t pkts_lost;

    seq_no_t curr_expected_seq_no; 
    bit<8> hard_coded_36;

    seq_no_t curr_ack;
    bit<16> timeout_val;
    seq_no_t pkt_seq_no;
    seq_no_t min_val;
    bit<1> curr_ack_era;
    bit<8> blocking_mode_orig_ig_port;

    random_gen_bitwidth_t curr_rand_number;

    bit<1> ack_timeout_triggered; 


    #if MEASURE_RETX_LATENCY
    bit<32> lost_timestamp;
    #endif
}

struct eg_metadata_t {
    bridged_meta_h bridged_meta;
    ig_mirror_lack_update_h ig_mirror_lack_update;
    ig_mirror_loss_notification_h ig_mirror_loss_notification;
    eg_mirror_courier_pkt_h eg_mirror_courier_pkt;
    eg_mirror_pfc_pkt_h eg_mirror_pfc_pkt;
    // eg_mirror_affected_flow_h eg_mirror_affected_flow;
    bit<8> leading_ack_notify_max_count;
    bit<1> is_lack_pending;
    bit<1> debug;

    bit<1> exceeded_ecn_marking_threshold;
    bit<1> exceeded_recirc_buffer_pfc_pause_threshold;
    bit<1> subceeded_recirc_buffer_pfc_resume_threshold;
    bit<1> should_send_pfc_pause;
    bit<1> should_send_pfc_resume;
    bit<16> pfc_quanta;
    bit<8> pfc_gen_req;
    bit<1> either_rx_buffered_or_timer_pfc;

    // #if DEBUG  // BUG: somehow macro not working here
    bit<32> pause_ts_idx;
    bit<32> resume_ts_idx; 
    bit<32> qdepth_record_idx;
    // #endif

    MirrorId_t mirror_session; 
    internal_hdr_type_t internal_hdr_type; 
    internal_hdr_info_t internal_hdr_info;
}


#endif
