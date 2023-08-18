/* -*- P4_16 -*- */
#include <core.p4>
#if __TARGET_TOFINO__ == 2
#include <t2na.p4>
#else
#include <tna.p4>
#endif

#include "includes/headers.p4"
#include "includes/parser.p4"


const int MCAST_GRP_ID = 1; // for ARP

// const int MIRROR_SESSION_TINA_ENS2F0 = 1;
// const int TINA_ENS2F0_ETH_ADDR = 0x6cb3115309b0;

// Deflection ports for reporting affected flows
#define INFO_DEV_PORT_TINA_ENS2F0 56
#define INFO_DEV_PORT_LUMOS_ENS3F0 132
#define INFO_DEV_PORT_PATRONUS_ENS1F1 147

const int RECEIVER_SW_ADDR = 0xAABBCCDDEEFF;
const int SENDER_SW_ADDR = 0xAAAABBBBCCCC;

// #ifndef LR_SETUP
// #error Please specify -DLR_SETUP=1 or -DLR_SETUP=2 to p4_build.sh script
// #endif

// #if LR_SETUP == 1
// const int TELEMETRY_DEV_PORT = INFO_DEV_PORT_TINA_ENS2F0;
// #elif LR_SETUP == 2
const int TELEMETRY_DEV_PORT = INFO_DEV_PORT_PATRONUS_ENS1F1;
// #endif

const int MAX_PORTS = 256;
const int EMULATED_DROP_TYPE_SELECTIVE = 1;
const int EMULATED_DROP_TYPE_RANDOM = 2;

control SwitchIngress(
    inout header_t hdr,
    inout metadata_t meta,
    in ingress_intrinsic_metadata_t ig_intr_md,
    in ingress_intrinsic_metadata_from_parser_t ig_intr_md_from_prsr,
    inout ingress_intrinsic_metadata_for_deparser_t ig_intr_md_for_dprsr,
    inout ingress_intrinsic_metadata_for_tm_t ig_intr_md_for_tm){

	Counter<bit<64>,bit<1>>(1,CounterType_t.PACKETS_AND_BYTES) dedup_drop_counter;

	action nop(){}

	action drop(){
		ig_intr_md_for_dprsr.drop_ctl = 0b001;
	}

	action miss(bit<3> drop_bits) {
		ig_intr_md_for_dprsr.drop_ctl = drop_bits;
	}

	action forward(PortId_t port){
		ig_intr_md_for_tm.ucast_egress_port = port;
	}

	table l2_forward {
		key = {
			meta.port_md.switch_id: exact;
			hdr.ethernet.dst_addr: exact;
		}

		actions = {
			forward;
			@defaultonly miss;
		}

		const default_action = miss(0x1);

	}

	Register<bit<16>,bit<8>>(MAX_PORTS, 0) reg_tcp_data_pkt_cntr; // default=0
	RegisterAction<bit<16>,bit<8>,bit<16>>(reg_tcp_data_pkt_cntr)
	get_next_data_pkt_count = {
		void apply(inout bit<16> reg_val, out bit<16> rv){
			reg_val = reg_val + 1;
			rv = reg_val;
		}
	};

	action get_incr_tcp_data_pkt_count(){
		meta.tcp_data_pkt_count = get_next_data_pkt_count.execute(0);
	}

	// Counter<bit<64>,bit<8>>(256, CounterType_t.PACKETS_AND_BYTES) emulate_pkt_drop_stats;

	action do_emulate_pkt_drop(){
		// Redirect the pkt to affected_flows monitoring
		ig_intr_md_for_tm.ucast_egress_port = TELEMETRY_DEV_PORT;
		// emulate_pkt_drop_stats.count(1);
	}

	action nop_emulate_pkt_drop(){
		// emulate_pkt_drop_stats.count(0);
	}

	table emulate_tcp_data_pkt_drop {
		key = {
			meta.tcp_data_pkt_count: exact;
		}
		actions = {
			do_emulate_pkt_drop;
			nop_emulate_pkt_drop;
		}
		const default_action = nop_emulate_pkt_drop();
		size = 1;
	}

	Register<bit<8>,bit<1>>(1, 0) reg_prev_drop; // 1 entry, default value 0
	RegisterAction<bit<8>,bit<1>,bit<1>>(reg_prev_drop) get_set_prev_drop = { 
		// called when random dropper indicated to drop
		void apply(inout bit<8> reg_val, out bit<1> rv){
			rv = (bit<1>)reg_val; 
			if(reg_val == 1){ // if prev was dropped
				// outside logic won't drop this one
				// so mark as not dropped
				reg_val = 0;
			}
			else{ // prev was not dropped. But this is being dropped
				// so record as dropped
				reg_val = 1;
			}
		}
	};
	action check_record_prev_drop(){
		meta.prev_dropped = get_set_prev_drop.execute(0);
	}
	action reset_prev_drop(){
		reg_prev_drop.write(0,0); // idx 0, value 0
	}

	action decide_random_pkt_drop(){
		meta.drop_decision = 1;
	}

	table emulate_random_pkt_drop {
		key = {
			meta.curr_rand_number: exact;
		}
		actions = {
			// decide_random_pkt_drop;
			do_emulate_pkt_drop;
			nop_emulate_pkt_drop;
		}
		const default_action = nop_emulate_pkt_drop();
		size = RANDOM_DROP_TABLE_SIZE;
	}

	Counter<bit<64>,bit<8>>(256, CounterType_t.PACKETS_AND_BYTES) check_if_tcp_data_pkt_stats;

	action mark_as_tcp_data_pkt(){
		check_if_tcp_data_pkt_stats.count(1);
	}

	action nop_check_if_tcp_data_pkt(){
		check_if_tcp_data_pkt_stats.count(0);
	}

	table check_if_tcp_data_pkt {
		key = {
			hdr.tcp.isValid(): exact;
			hdr.ipv4.total_len: range;
		}
		actions = {
			mark_as_tcp_data_pkt;
			nop_check_if_tcp_data_pkt;
		}
		const default_action = nop_check_if_tcp_data_pkt();
		const entries = {
			(true, 81..1600): mark_as_tcp_data_pkt();
		}
		size = 1;
	}

	Register<bit<8>,bit<1>>(1,0) reg_emulated_drop_type;
	action get_emulated_drop_type(){
		meta.emulated_drop_type = reg_emulated_drop_type.read(0)[1:0];
	}

	Random<random_gen_bitwidth_t>() random; 

	action get_curr_random_number(){
		meta.curr_rand_number = random.get();
	}

/*
		Register<bit<32>,bit<1>>(1,0) reg_tcp_seq_idx;
	RegisterAction<bit<32>,bit<1>,bit<32>>(reg_tcp_seq_idx) read_incr_tcp_seq_idx = {
		void apply(inout bit<32> reg_val, out bit<32> rv){
			rv = reg_val;

			if(reg_val < MAX_PKT_RECORDS){
				reg_val = reg_val + 1;
			}
		}
	};

	Register<bit<32>,bit<32>>(MAX_PKT_RECORDS, 0) reg_tcp_seq_nos;

	action get_tcp_seq_no_idx(){
		eg_meta.tcp_seq_no_idx = read_incr_tcp_seq_idx.execute(0);
	}

	action record_tcp_seq_no(){
		reg_tcp_seq_nos.write(eg_meta.tcp_seq_no_idx, hdr.tcp.seq_no);
	}

	// #if DEBUG
			// if(hdr.tcp.isValid() && eg_intr_md.egress_port==52){
			// 	get_tcp_seq_no_idx();
			// 	record_tcp_seq_no();
			// }
			// #endif */

#ifdef RDMA_MONITORING
	/** @brief Memorize seq of last WRITE */
	Register<bit<32>, bit<1>>(1) reg_last_seq;
    RegisterAction<bit<32>, bit<1>, bit<32>>(reg_last_seq) reg_last_seq_write = {
		void apply(inout bit<32> value, out bit<32> result) {
			if (meta.ig_mirror1.opcode == 8w6) {
				value = OUT_OF_RANGE_24BIT;
			} else {
            	value = meta.ig_mirror1.rdma_seqnum;
			}
		}
	};
    RegisterAction<bit<32>, bit<1>, bit<8>>(reg_last_seq) reg_last_seq_match = {
		void apply(inout bit<32> value, out bit<8> result) {
            if (value == meta.ig_mirror1.rdma_seqnum) {
                result = 8w1;
            } else {
                result = 8w0;
            }
		}
	};
    action action_reg_last_seq_write() {
        reg_last_seq_write.execute(0);
    }
    action action_reg_last_seq_match() {
        meta.ig_mirror1.last_ack = reg_last_seq_match.execute(0); // check last ack or not
    }

	action get_seqnum_to_metadata() {
        meta.ig_mirror1.rdma_seqnum = (bit<32>)hdr.bth.packet_seqnum;
    }

    /** @brief Mirroring packets to Sniff Port */
    action mirror_to_collector(bit<10> ing_mir_ses){
        ig_intr_md_for_dprsr.mirror_type = IG_MIRROR_TYPE_1;
        meta.mirror_session = ing_mir_ses;
		meta.ig_mirror1.ingress_mac_timestamp = ig_intr_md.ingress_mac_tstamp;
		meta.ig_mirror1.opcode = hdr.bth.opcode;
		meta.ig_mirror1.mirrored = (bit<8>)IG_MIRROR_TYPE_1;
    }
#endif

	action remove_pktgen_add_ether(){
        hdr.pktgen_timer.setInvalid();
        hdr.remaining_ethernet.setInvalid();

        hdr.ethernet.setValid();
        hdr.ethernet.dst_addr = RECEIVER_SW_ADDR; 
        hdr.ethernet.src_addr = SENDER_SW_ADDR; 

        hdr.ethernet.ether_type = ether_type_t.PKTGEN;
    }

	Register<bit<32>,bit<1>>(1) reg_dedup_ts;
	RegisterAction<bit<32>,bit<1>,bit<1>>(reg_dedup_ts) check_reset_dedup_ts = {
		void apply(inout bit<32> reg_val, out bit<1> rv){
			if (reg_val == hdr.ethernet.src_addr[31:0]){
				rv = 1;
			}
			else{
				rv = 0;
			}
			reg_val = hdr.ethernet.src_addr[31:0];
		}
	};

	action do_check_reset_dedup_ts(){
		meta.is_same_ts = check_reset_dedup_ts.execute(0);
	}

	apply {

		if(hdr.ethernet.ether_type == (bit<16>) ether_type_t.ARP){
			// do the broadcast to all involved ports
			ig_intr_md_for_tm.mcast_grp_a = MCAST_GRP_ID;
			ig_intr_md_for_tm.rid = 0;
		}
		else { // non-arp packet
			
			if (meta.port_md.switch_id == 2) { 
#ifdef RDMA_MONITORING
				if (hdr.bth.isValid()){
					mirror_to_collector(10w777); // mirror all RDMA packets
					get_seqnum_to_metadata();
					if (meta.ig_mirror1.opcode == 8w6 || meta.ig_mirror1.opcode == 8w8 || meta.ig_mirror1.opcode == 8w10) {
						action_reg_last_seq_write(); // record seqnum of FIRST WRITE
					} else if (meta.ig_mirror1.opcode == 8w17) {
						action_reg_last_seq_match(); // check ACK for the LAST WRITE
					}
				}
#endif
			}
			else if (meta.port_md.switch_id == 2){ // pktgen pkts will have switch_id 2
				if(hdr.pktgen_timer.isValid()){ // Pktgen pkt received on dev_port 68. 
					remove_pktgen_add_ether();
					// NOTE: L2 forward will do the appropriate forwarding
				}
			}
			else if (meta.port_md.switch_id == 3){
				// *** Tofino-based dropping + affected flows reporting
				if(ig_intr_md.ingress_port == 164){

					if(hdr.ethernet.ether_type == ether_type_t.PKTGEN){
						drop();
						// NOTE: l2_forward should drop it for lack of matching entry
						// BUT, still dropping here explicitly
					}

					// get_emulated_drop_type.apply(); // sets meta.emulated_drop_type
					get_emulated_drop_type();
					if(meta.emulated_drop_type == EMULATED_DROP_TYPE_SELECTIVE){
						// check_if_tcp_data_pkt.apply(); // sets meta.is_tcp_data_pkt
						if(check_if_tcp_data_pkt.apply().hit){    // (meta.is_tcp_data_pkt == 1){ // TCP data pkt
							get_incr_tcp_data_pkt_count(); // sets meta.tcp_data_pkt_count
							emulate_tcp_data_pkt_drop.apply(); // matches on meta.tcp_data_pkt_count
						}
					}
					else if(meta.emulated_drop_type == EMULATED_DROP_TYPE_RANDOM){
						get_curr_random_number(); // fills meta.curr_rand_number
						emulate_random_pkt_drop.apply(); // redirect pkt OLD:sets meta.drop_decision

						// if(meta.drop_decision == 1){
						// 	check_record_prev_drop(); // gives meta.prev_dropped
						// 	if(meta.prev_dropped == 0){ // previous was not dropped. So drop current one.
						// 		do_emulate_pkt_drop();
						// 	}
						// 	else{ // previous was dropped. Don't drop current
						// 		// nop. Not honoring the drop_decision
						// 	}
						// }
						// else{ // meta.drop_decision == 0
						// 	reset_prev_drop(); 
						// }
					}
				}
			}

			l2_forward.apply();

			// ONLY for computing switch-to-switch effective link speed for NB mode
			if (hdr.ethernet.src_addr[47:40] == 0xAA){
			// This is because the LG Rx switch marks ReTx pkts with 0xAA
				do_check_reset_dedup_ts(); // sets meta.is_same_ts

				if(meta.is_same_ts == 1){
					drop();
					dedup_drop_counter.count(0);
				}
			}
		}

		// pass ingress_mac_ts to egress for every pkt
		// ingress parser sets the remaining stuff in hdr.bridged_meta
		/*
		NOTE: commented out for now. Since not needed for Tofino-based dropping
		hdr.bridged_meta.ig_mac_ts = ig_intr_md.ingress_mac_tstamp[31:0];
		*/

		// Allow egress processing for all switches 
		// ig_intr_md_for_tm.bypass_egress = 1w1; 
	}

}  // End of SwitchIngressControl

control SwitchEgress(
    inout header_t hdr,
    inout metadata_t meta,
    in egress_intrinsic_metadata_t eg_intr_md,
    in egress_intrinsic_metadata_from_parser_t eg_intr_md_from_prsr,
    inout egress_intrinsic_metadata_for_deparser_t eg_intr_md_for_dprsr,
    inout egress_intrinsic_metadata_for_output_port_t eg_intr_md_for_oport){

	Register<bit<32>,bit<1>>(1,524287) reg_ecn_marking_threshold; // default = 2^19 - 1 
	RegisterAction<bit<32>,bit<1>,bit<1>>(reg_ecn_marking_threshold) cmp_ecn_marking_threshold = {
		void apply(inout bit<32> reg_val, out bit<1> rv){
			if((bit<32>)eg_intr_md.deq_qdepth >= reg_val){
				rv = 1;
			}
			else{
				rv = 0;
			}
		}
	};

	action check_ecn_marking_threshold(){
		meta.exceeded_ecn_marking_threshold = cmp_ecn_marking_threshold.execute(0);
	}

	action mark_ecn_ce_codepoint(){
		hdr.ipv4.ecn = 0b11;
	}

	/*

	Register<bit<8>,bit<1>>(1,0) reg_seq_no;

	RegisterAction<bit<8>,bit<1>,bit<8>>(reg_seq_no) get_next_seq_no = {
		void apply(inout bit<8> reg_val, out bit<8> rv){
			rv = reg_val;
			reg_val = reg_val + 1;
		}
	};

	Register<bit<8>,bit<1>>(1,0) reg_expected_seq_no;
	RegisterAction<bit<8>,bit<1>,bit<8>>(reg_expected_seq_no) do_get_update_expected_seq_no = {
		void apply(inout bit<8> reg_val, out bit<8> rv){
			rv = reg_val;
			reg_val = hdr.linkradar.seq_no + 1;
		}
	};

	Register<bit<32>, bit<1>>(1, 0) reg_hole_count;
	RegisterAction<bit<32>, bit<1>, bit<32>>(reg_hole_count)
	do_update_hole_count = {
		void apply(inout bit<32> reg_val, out bit<32> rv){
			reg_val = reg_val + 1;
		}
	};

	Register<bit<32>, bit<1>>(1, 0) reg_last_mac_ts;
	RegisterAction<bit<32>, bit<1>, bit<32>>(reg_last_mac_ts)
	do_read_update_last_mac_ts = {
		void apply(inout bit<32> reg_val, out bit<32> rv){
			rv = reg_val;
			reg_val = meta.bridged.ig_mac_ts;
		}
	};
	
	action read_update_last_mac_ts(){
		meta.prev_mac_ts = do_read_update_last_mac_ts.execute(0);
	}

	action update_hole_count(){
		do_update_hole_count.execute(0);
	}

	action get_update_expected_seq_no(){
		meta.expected_seq_no = do_get_update_expected_seq_no.execute(0);
	}

	action encap(){
		hdr.ethernet.ether_type = (bit<16>)ether_type_t.LINKRADAR;
		hdr.linkradar.setValid();
		hdr.linkradar.seq_no = get_next_seq_no.execute(0);
	}

	action decap(){
		hdr.ethernet.ether_type = (bit<16>)ether_type_t.IPV4;
		hdr.linkradar.setInvalid();
	}

	action calc_pkts_lost(){
		meta.pkts_lost = (hdr.linkradar.seq_no - meta.expected_seq_no);
	}
	
	action mirror_to_report_affected_flow(){
		eg_intr_md_for_dprsr.mirror_type = EG_MIRROR_TYPE_1;
		meta.mirror_session = MIRROR_SESSION_TINA_ENS2F0;
		meta.internal_hdr_type = INTERNAL_HDR_TYPE_EG_MIRROR;
    	meta.internal_hdr_info = (bit<4>)EG_MIRROR_TYPE_1;

		meta.hole_size_to_report = meta.pkts_lost;
		meta.ipg_to_report = meta.bridged.ig_mac_ts - meta.prev_mac_ts;
	}
	*/

	apply{

#ifdef RDMA_MONITORING
		if (meta.ig_mirror1.mirrored == (bit<8>)IG_MIRROR_TYPE_1) {
			/* Last ACK: egress_timestamp -> MAC Src address */
			if (meta.ig_mirror1.last_ack == 8w1) { // if not mirrored, it will be 0
				hdr.ethernet.src_addr = eg_intr_md_from_prsr.global_tstamp; // 48 bits
			} else {
			/* other packets: ingress_timestamp -> MAC Src address */
				hdr.ethernet.src_addr = meta.ig_mirror1.ingress_mac_timestamp; // 48 bits
			}

			/* Sequence Number -> MAC Dst address */
			hdr.ethernet.dst_addr = (bit<48>)meta.ig_mirror1.rdma_seqnum;
		}
#endif

		if(hdr.ipv4.ecn == 0b01 || hdr.ipv4.ecn == 0b10){
			check_ecn_marking_threshold(); // fills meta.exceeded_ecn_marking_threshold
			if(meta.exceeded_ecn_marking_threshold == 1){
				mark_ecn_ce_codepoint();
			}
		}
		/*
		NOTE: [OLD] commented out for now. Not needed for Tofino-based dropping
		// IPG Calculation
		read_update_last_mac_ts();

		if(eg_intr_md.egress_port == 172){ // encap at TX switch (sw1) 
			// protect all IPv4 packets
			if(hdr.ipv4.isValid()){
				encap();
			}
		}
		else if(eg_intr_md.egress_port == 142){ // check + decap at RX switch (sw2)
			if(hdr.linkradar.isValid()){ // check for encaped packets only
				// get expected seq no and also update it
				get_update_expected_seq_no();

				// get diff between curr and expected seq no
				calc_pkts_lost();
				
				if(meta.pkts_lost != 0 && hdr.tcp.isValid()){ // some packets were lost
					update_hole_count();
					mirror_to_report_affected_flow();
				}

				// remove the linkradar header
				decap();
				
			}
		}
		else if(eg_intr_md.egress_port == INFO_DEV_PORT_TINA_ENS2F0){ // mirrored packet
			hdr.ethernet.dst_addr = TINA_ENS2F0_ETH_ADDR; // change just dst addr for now
			hdr.ethernet.src_addr = 16w0 ++ meta.eg_mirror1.ipg;
			hdr.ipv4.ttl = meta.eg_mirror1.hole_size;
		}
		*/ 
		// Making sure to remove the bridged_meta before sending on wire
		// hdr.bridged_meta.setInvalid(); 

	} // end of apply block

} // End of SwitchEgress


Pipeline(SwitchIngressParser(),
		 SwitchIngress(),
		 SwitchIngressDeparser(),
		 SwitchEgressParser(),
		 SwitchEgress(),
		 SwitchEgressDeparser()
		 ) pipe;

Switch(pipe) main;

