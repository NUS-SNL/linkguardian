#ifndef _PARSER_
#define _PARSER_

#define IP_PROTOCOL_UDP 17
#define IP_PROTOCOL_TCP 6


enum bit<16> ether_type_t {
    IPV4 = 0x0800,
    ARP  = 0x0806,
    PKTGEN = 0xBFBF,
    LINKRADAR = 0xABCD
}

enum bit<8> ipv4_proto_t {
    TCP = 6,
    UDP = 17
}

enum bit<16> udp_proto_t {
    ROCE_V2 = 4791
}


// ---------------------------------------------------------------------------
// Ingress parser
// ---------------------------------------------------------------------------
parser SwitchIngressParser(
    packet_in pkt,
    out header_t hdr,
    out ig_metadata_t ig_meta,
    out ingress_intrinsic_metadata_t ig_intr_md,
    out ingress_intrinsic_metadata_for_tm_t ig_intr_md_for_tm,
    out ingress_intrinsic_metadata_from_parser_t ig_intr_md_from_prsr){


	state start {
        pkt.extract(ig_intr_md);
        pkt.advance(PORT_METADATA_SIZE); // macro defined in tofino.p4

        transition init_metadata;        
	}

    state init_metadata { // init bridged and other ig_meta (based on slide 23 of BA-1122)
        ig_meta.is_missing_hole_1 = 0;
        ig_meta.is_missing_hole_2 = 0;
        ig_meta.is_missing_hole_3 = 0;
        ig_meta.is_missing_hole_4 = 0;
        ig_meta.is_missing_hole_5 = 0;
        ig_meta.curr_era = 0;
        transition parse_pktgen_or_ethernet;
    }

    state parse_pktgen_or_ethernet {
        ethernet_h ethernet_lookahead = pkt.lookahead<ethernet_h>();
        transition select(ethernet_lookahead.ether_type){
            (bit<16>) ether_type_t.PKTGEN : parse_pktgen_timer;
            default: parse_ethernet;
        }
    }

    state parse_pktgen_timer {
        pkt.extract(hdr.pktgen_timer);
        pkt.extract(hdr.remaining_ethernet);
        transition accept;
    }

   	state parse_ethernet {
		pkt.extract(hdr.ethernet);
		transition select(hdr.ethernet.ether_type){
			(bit<16>) ether_type_t.IPV4: parse_ipv4;
			(bit<16>) ether_type_t.ARP: parse_arp;
            (bit<16>) ether_type_t.LINKRADAR: parse_linkradar;
			default: accept;
		}
	}

    state parse_linkradar {
        linkradar_hdr_type_t lr_hdr_type;
        lr_hdr_type = pkt.lookahead<linkradar_hdr_type_t>();
        
        transition select(lr_hdr_type){
            LINKRADAR_HDR_TYPE_DATA: parse_linkradar_data;
            LINKRADAR_HDR_TYPE_LACK: parse_linkradar_lack;
            LINKRADAR_HDR_TYPE_LACK_LOSS_NOTIFY: parse_linkradar_lack_loss_notification;
            LINKRADAR_HDR_TYPE_TX_BUFFERED: parse_linkradar_buffered_pkt;
        }
    }

    state parse_linkradar_data {
        pkt.extract(hdr.linkradar_data);
        transition accept;
    }
    state parse_linkradar_lack {
        pkt.extract(hdr.linkradar_lack);
        transition accept;
    }
    state parse_linkradar_lack_loss_notification {
        pkt.extract(hdr.linkradar_lack);
        pkt.extract(hdr.linkradar_loss_notification);
        ig_meta.first_lost_seq_no_copy = hdr.linkradar_loss_notification.first_lost_seq_no;
        transition accept;
    }
    state parse_linkradar_buffered_pkt {
        pkt.extract(hdr.linkradar_buffered);
        pkt.extract(hdr.linkradar_data);
        ig_meta.buffered_seq_no = hdr.linkradar_data.seq_no; // copy seq_no to ig_meta
        transition accept;
    }

	state parse_ipv4 {
		pkt.extract(hdr.ipv4);
		transition select(hdr.ipv4.protocol){
			(bit<8>) ipv4_proto_t.TCP: parse_tcp;
			(bit<8>) ipv4_proto_t.UDP: parse_udp;
		    default: accept;
		}
	}

	state parse_arp {
		pkt.extract(hdr.arp);
		transition accept;
	}

	state parse_tcp {
		pkt.extract(hdr.tcp);
		transition accept;
	}

	state parse_udp {
		pkt.extract(hdr.udp);
		transition accept;
	}
}


// ---------------------------------------------------------------------------
// Ingress Deparser
// ---------------------------------------------------------------------------
control SwitchIngressDeparser(
        packet_out pkt,
        inout header_t hdr,
        in ig_metadata_t ig_meta,
        in ingress_intrinsic_metadata_for_deparser_t ig_dprsr_md) {

    Checksum() ipv4_checksum;

    apply {
        hdr.ipv4.hdr_checksum = ipv4_checksum.update({
            hdr.ipv4.version,
            hdr.ipv4.ihl,
            hdr.ipv4.dscp,
            hdr.ipv4.ecn,
            hdr.ipv4.total_len,
            hdr.ipv4.identification,
            hdr.ipv4.flags,
            hdr.ipv4.frag_offset,
            hdr.ipv4.ttl,
            hdr.ipv4.protocol,
            hdr.ipv4.src_addr,
            hdr.ipv4.dst_addr});

         pkt.emit(hdr);
    }
}


// ---------------------------------------------------------------------------
// Egress parser
// ---------------------------------------------------------------------------
parser SwitchEgressParser(
    packet_in pkt,
    out header_t hdr,
    out eg_metadata_t eg_meta,
    out egress_intrinsic_metadata_t eg_intr_md,
    out egress_intrinsic_metadata_from_parser_t eg_intr_md_from_prsr){

    internal_hdr_h internal_hdr;

    state start {
        pkt.extract(eg_intr_md);

        internal_hdr = pkt.lookahead<internal_hdr_h>();
        transition select(internal_hdr.type, internal_hdr.info){
            (INTERNAL_HDR_TYPE_BRIDGED_META, _): parse_bridged_meta;
            (INTERNAL_HDR_TYPE_EG_MIRROR, (bit<4>)EG_MIRROR_BUFFERED_PKT): parse_eg_mirror_buffered_pkt;
            (INTERNAL_HDR_TYPE_EG_MIRROR, (bit<4>)EG_MIRROR_DUMMY_PKT):
            parse_eg_mirror_dummy_pkt;
            (INTERNAL_HDR_TYPE_EG_MIRROR_AFFECTED_FLOW, EG_MIRROR_AFFECTED_FLOW_UNPROTECTED): parse_eg_mirror_affected_flow_unprotected;
            (INTERNAL_HDR_TYPE_EG_MIRROR_AFFECTED_FLOW, EG_MIRROR_AFFECTED_FLOW_PROTECTED): parse_eg_mirror_affected_flow_protected;
        }
    }

    state parse_bridged_meta {
        pkt.extract(eg_meta.bridged_meta);
        transition parse_ethernet;
    }

    state parse_eg_mirror_buffered_pkt {
        pkt.extract(eg_meta.eg_mirror_buffered_pkt);
        pkt.extract(hdr.ethernet);
        pkt.extract(hdr.linkradar_data); // LOGIC: to distinguish from normal pkt in eg ctrl
        transition accept;
    }

    state parse_eg_mirror_dummy_pkt {
        // just get rid of the internal header
        // TODO: try advance() and save some PHV
        pkt.extract(eg_meta.eg_mirror_dummy_pkt);
        transition parse_ethernet;
    }

    state parse_eg_mirror_affected_flow_unprotected {
        pkt.extract(eg_meta.eg_mirror_affected_flow);
        transition parse_ethernet;
    }

    state parse_eg_mirror_affected_flow_protected {
        pkt.extract(eg_meta.eg_mirror_affected_flow);
        pkt.extract(hdr.ethernet);
        pkt.extract(hdr.linkradar_buffered);
        pkt.extract(hdr.linkradar_data);
    }

    state parse_ethernet {
    	pkt.extract(hdr.ethernet);
        transition select(hdr.ethernet.ether_type){
            (bit<16>) ether_type_t.LINKRADAR : parse_linkradar;
            (bit<16>) ether_type_t.IPV4: parse_ipv4;
            default: accept; 
        }
    }

    // state parse_ipv4 {
	// 	pkt.extract(hdr.ipv4);
    //     transition accept;
    // }

    state parse_ipv4 {
		pkt.extract(hdr.ipv4);
		transition select(hdr.ipv4.protocol){
			// (bit<8>) ipv4_proto_t.TCP: parse_tcp;
			(bit<8>) ipv4_proto_t.UDP: parse_udp;
		    default: accept;
		}
	}

    state parse_udp {
		pkt.extract(hdr.udp);
        transition select(hdr.udp.dst_port){
            udp_proto_t.ROCE_V2: parse_roce_v2;
            default: accept;
        }
	}

    state parse_roce_v2{
        eg_meta.is_roce_v2 = 1;
        transition accept;
    }

    state parse_linkradar {
        linkradar_hdr_type_t lr_hdr_type;
        lr_hdr_type = pkt.lookahead<linkradar_hdr_type_t>();
        
        transition select(lr_hdr_type){
            LINKRADAR_HDR_TYPE_TX_BUFFERED: parse_linkradar_buffered_pkt;
            LINKRADAR_HDR_TYPE_DATA: parse_linkradar_data;
            default: accept;    
        }
    }

    state parse_linkradar_buffered_pkt {
        pkt.extract(hdr.linkradar_buffered);
        pkt.extract(hdr.linkradar_data);
        transition accept;
    }

    state parse_linkradar_data {
        pkt.extract(hdr.linkradar_data);
        transition accept;
    }



    // do more stuff here if needed
}

// ---------------------------------------------------------------------------
// Egress Deparser
// ---------------------------------------------------------------------------
control SwitchEgressDeparser(
    packet_out pkt,
    inout header_t hdr,
    in eg_metadata_t eg_meta,
    in egress_intrinsic_metadata_for_deparser_t eg_intr_md_for_dprsr,
    in egress_intrinsic_metadata_t eg_intr_md,
    in egress_intrinsic_metadata_from_parser_t eg_intr_md_from_prsr){
    
    Mirror() mirror;
    Checksum() ipv4_checksum;

	apply{
        if(eg_intr_md_for_dprsr.mirror_type == EG_MIRROR_BUFFERED_PKT){
            mirror.emit<eg_mirror_buffered_pkt_h>(eg_meta.mirror_session, 
            {   eg_meta.internal_hdr_type,
                eg_meta.internal_hdr_info,
                0,
                eg_meta.emulated_dropped,
                eg_meta.dst_eg_port
            });
        }
        else if(eg_intr_md_for_dprsr.mirror_type == EG_MIRROR_DUMMY_PKT){
            mirror.emit<eg_mirror_dummy_pkt_h>(eg_meta.mirror_session, 
            {   eg_meta.internal_hdr_type,
                eg_meta.internal_hdr_info
            });
        }
        else if(eg_intr_md_for_dprsr.mirror_type == EG_MIRROR_AFFECTED_FLOW){
            mirror.emit<eg_mirror_affected_flow_h>(eg_meta.mirror_session, 
            {   eg_meta.internal_hdr_type,
                eg_meta.internal_hdr_info  // can hv two types
            });
        }

        hdr.ipv4.hdr_checksum = ipv4_checksum.update({
            hdr.ipv4.version,
            hdr.ipv4.ihl,
            hdr.ipv4.dscp,
            hdr.ipv4.ecn,
            hdr.ipv4.total_len,
            hdr.ipv4.identification,
            hdr.ipv4.flags,
            hdr.ipv4.frag_offset,
            hdr.ipv4.ttl,
            hdr.ipv4.protocol,
            hdr.ipv4.src_addr,
            hdr.ipv4.dst_addr});

		pkt.emit(hdr);
	}

}







#endif