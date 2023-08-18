#ifndef _PARSER_
#define _PARSER_

#define IP_PROTOCOL_UDP 17
#define IP_PROTOCOL_TCP 6


enum bit<16> ether_type_t {
    IPV4 = 0x0800,
    ARP  = 0x0806,
    PKTGEN = 0xBFBF,
    LINKRADAR = 0xABCD,
    PAUSE_PFC = 0x8808
}

enum bit<8> ipv4_proto_t {
    TCP = 6,
    UDP = 17
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
        transition parse_port_metadata;
    }

    state parse_port_metadata {
        ig_meta.port_md = port_metadata_unpack<port_metadata_t>(pkt);
        transition init_metadata;
    }

    state init_metadata { // init bridged and other ig_meta (based on slide 23 of BA-1122)
        // TODO: init essential metadata here. CAUTION: should not affect filtering via lpbk logic
        ig_meta.ack_timeout_triggered = 0;
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
        pkt.extract(hdr.ether_pfc); 
        transition accept;
    }

   	state parse_ethernet {
		pkt.extract(hdr.ethernet);
		transition select(hdr.ethernet.ether_type){
			// (bit<16>) ether_type_t.IPV4: parse_ipv4;
			(bit<16>) ether_type_t.ARP: parse_arp;
            (bit<16>) ether_type_t.LINKRADAR: parse_linkradar;
			default: accept;
		}
	}

    state parse_arp {
		pkt.extract(hdr.arp);
		transition accept;
	}

    state parse_linkradar {
        linkradar_hdr_type_t lr_hdr_type;
        lr_hdr_type = pkt.lookahead<linkradar_hdr_type_t>();
        
        transition select(lr_hdr_type){
            LINKRADAR_HDR_TYPE_DATA: parse_linkradar_data;
            LINKRADAR_HDR_TYPE_LACK: parse_linkradar_lack;
            default: accept;
        }
        // pkt.extract(hdr.linkradar_data);
        // transition accept;
    }

    state parse_linkradar_data {
        pkt.extract(hdr.linkradar_data);
        ig_meta.pkt_seq_no = hdr.linkradar_data.seq_no;
        // transition accept;
        transition select(hdr.linkradar_data.rx_buffered){
            #if MEASURE_RETX_LATENCY
            0: parse_ipv4;
            #else
            0: accept;
            #endif
            1: parse_linkradar_rx_buffered;
        }
    }

    state parse_linkradar_rx_buffered {
        pkt.extract(hdr.linkradar_rx_buffered);
        transition accept;
    }

    state parse_linkradar_lack {
        pkt.extract(hdr.linkradar_lack);
        transition accept;
    }

    state parse_ipv4 {
		pkt.extract(hdr.ipv4);
        transition accept;
	}

/* 
	state parse_ipv4 {
		pkt.extract(hdr.ipv4);

        transition select(hdr.ipv4.protocol, hdr.ipv4.total_len){	
            ((bit<8>) ipv4_proto_t.TCP, 60..65535): parse_tcp_data; // longer parsing
            ((bit<8>) ipv4_proto_t.TCP, _): parse_tcp;
            ((bit<8>) ipv4_proto_t.UDP, _): parse_udp;
            default: accept;
        }
		
	}
*/
 
/* 
	state parse_tcp {
		pkt.extract(hdr.tcp);
		transition accept;
	}

	state parse_udp {
		pkt.extract(hdr.udp);
		transition accept;
	}
*/ 

}


// ---------------------------------------------------------------------------
// Ingress Deparser
// ---------------------------------------------------------------------------
control SwitchIngressDeparser(
        packet_out pkt,
        inout header_t hdr,
        in ig_metadata_t ig_meta,
        in ingress_intrinsic_metadata_for_deparser_t ig_dprsr_md) {

    Mirror() mirror;

    apply {
        if(ig_dprsr_md.mirror_type == IG_MIRROR_LACK_UPDATE){
            mirror.emit<ig_mirror_lack_update_h>(ig_meta.mirror_session,
                {   ig_meta.internal_hdr_type,
                    ig_meta.internal_hdr_info,
                    ig_meta.ingress_port,
                    ig_meta.leading_ack,
                    0, // for the explicit padding
                    ig_meta.leading_ack_era
                }
            );
        }
        else if(ig_dprsr_md.mirror_type == IG_MIRROR_LOSS_NOTIFICATION){
            mirror.emit<ig_mirror_loss_notification_h>(ig_meta.mirror_session,
                {   ig_meta.internal_hdr_type,
                    ig_meta.internal_hdr_info,
                    ig_meta.pkts_lost,
                    ig_meta.expected_seq_no,
                    ig_meta.leading_ack,
                    0, // for the explicit padding
                    ig_meta.leading_ack_era
                    // ig_meta.from_dummy_pkt,
                }
            );
        }

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
            (INTERNAL_HDR_TYPE_IG_MIRROR, (bit<4>)IG_MIRROR_LACK_UPDATE): parse_ig_mirror_lack_update;
            (INTERNAL_HDR_TYPE_IG_MIRROR, (bit<4>)IG_MIRROR_LOSS_NOTIFICATION): parse_ig_mirror_loss_notification;
            (INTERNAL_HDR_TYPE_EG_MIRROR, (bit<4>)EG_MIRROR_COURIER_PKT): parse_eg_mirror_courier_pkt;
            (INTERNAL_HDR_TYPE_EG_MIRROR, (bit<4>)EG_MIRROR_PFC_PKT): parse_eg_mirror_pfc_pkt;
            // (INTERNAL_HDR_TYPE_EG_MIRROR, (bit<4>)EG_MIRROR_AFFECTED_FLOW): parse_eg_mirror_affected_flow;
        }
    }

    state parse_bridged_meta {
        pkt.extract(eg_meta.bridged_meta);
        transition parse_ethernet;
    }

    state parse_ig_mirror_lack_update { // just want the lack update. nothing else
        pkt.extract(eg_meta.ig_mirror_lack_update);
        transition accept;
    }

    state parse_ig_mirror_loss_notification {
        pkt.extract(eg_meta.ig_mirror_loss_notification);
        pkt.extract(hdr.ethernet);
        eg_meta.debug = 1;
        transition accept; // we have a truncated pkt. So stop here!
    }

    state parse_eg_mirror_courier_pkt {
        // just get rid of the internal header
        // TODO: try advance() and save some PHV
        pkt.extract(eg_meta.eg_mirror_courier_pkt);
        transition parse_ethernet;
    }

    state parse_eg_mirror_pfc_pkt {
        pkt.extract(eg_meta.eg_mirror_pfc_pkt);
        transition parse_ethernet_only;
    }

    // state parse_eg_mirror_affected_flow {
    //     // just get rid of the internal header
    //     // TODO: try advance() and save some PHV
    //     pkt.extract(eg_meta.eg_mirror_affected_flow);
    //     transition parse_ethernet;
    // }

    state parse_ethernet {
    	pkt.extract(hdr.ethernet);
        transition select(hdr.ethernet.ether_type){
            (bit<16>) ether_type_t.LINKRADAR : parse_linkradar;
            (bit<16>) ether_type_t.IPV4: parse_ipv4;
            (bit<16>) ether_type_t.PAUSE_PFC: parse_pfc;
            default: accept; 
        }
    }

    state parse_ethernet_only {
    	pkt.extract(hdr.ethernet);
        transition accept;
    }

    state parse_ipv4 {
		pkt.extract(hdr.ipv4);
        transition accept;
    }

    state parse_pfc {
        pkt.extract(hdr.ether_pfc);
        eg_meta.either_rx_buffered_or_timer_pfc = 1;
        transition accept;
    }

    state parse_linkradar {
        linkradar_hdr_type_t lr_hdr_type;
        lr_hdr_type = pkt.lookahead<linkradar_hdr_type_t>();
        
        transition select(lr_hdr_type){
            LINKRADAR_HDR_TYPE_DATA: parse_linkradar_data;
            LINKRADAR_HDR_TYPE_LACK: parse_linkradar_lack;
            default: accept;
        }
        // pkt.extract(hdr.linkradar_data);
        // transition accept;
    }

    state parse_linkradar_data {
        pkt.extract(hdr.linkradar_data);
        // transition accept;
        transition select(hdr.linkradar_data.rx_buffered){
            0: accept;
            1: parse_linkradar_rx_buffered;
        }
    }

    state parse_linkradar_rx_buffered {
        pkt.extract(hdr.linkradar_rx_buffered);
        eg_meta.either_rx_buffered_or_timer_pfc = 1;
        transition accept;
    }
    
    state parse_linkradar_lack {
        pkt.extract(hdr.linkradar_lack);
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
        if(eg_intr_md_for_dprsr.mirror_type == EG_MIRROR_COURIER_PKT){
            mirror.emit<eg_mirror_courier_pkt_h>(eg_meta.mirror_session, 
            {   eg_meta.internal_hdr_type,
                eg_meta.internal_hdr_info
            });
        }
        else if(eg_intr_md_for_dprsr.mirror_type == EG_MIRROR_PFC_PKT){
            mirror.emit<eg_mirror_pfc_pkt_h>(eg_meta.mirror_session, 
            {   eg_meta.internal_hdr_type,
                eg_meta.internal_hdr_info,
                eg_meta.pfc_quanta
            });
        }
        // else if(eg_intr_md_for_dprsr.mirror_type == EG_MIRROR_AFFECTED_FLOW){
        //     mirror.emit<eg_mirror_affected_flow_h>(eg_meta.mirror_session, 
        //     {   eg_meta.internal_hdr_type,
        //         eg_meta.internal_hdr_info
        //     });
        // }

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