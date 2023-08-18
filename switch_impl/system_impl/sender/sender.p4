/* -*- P4_16 -*- */
#include <core.p4>
#if __TARGET_TOFINO__ == 2
#include <t2na.p4>
#else
#include <tna.p4>
#endif

#ifndef MEASURE_RETX_LATENCY
#define MEASURE_RETX_LATENCY 0
#endif

#include "includes/headers.p4"
#include "includes/parser.p4"

#ifndef DEBUG
#define DEBUG 1
#endif

const int RECEIVER_SW_ADDR = 0xAABBCCDDEEFF;
const int SENDER_SW_ADDR = 0xAAAABBBBCCCC;
const int MAX_LACK_HOLE_RECORDS = 131072;
const int MAX_BUFFERED_DROPPED_RECORDS = 100000;
const int RECIRC_LPBK_PORT = 16; // 19/- FP port on tofino1a

#define DEBUG_COUNTER_IDX_WIDTH 4
#define DEBUG_COUNTER_SIZE 1<<DEBUG_COUNTER_IDX_WIDTH
typedef bit<DEBUG_COUNTER_IDX_WIDTH> debug_counter_idx_t;

// following pragma enables parallel lookup 
// of reg_holes_1..5 by buffered pkts within 2 stages
@pa_no_pack("ingress","ig_meta.is_missing_hole_1","ig_meta.is_missing_hole_2","ig_meta.is_missing_hole_3","ig_meta.is_missing_hole_4","ig_meta.is_missing_hole_5")
control SwitchIngress(
    inout header_t hdr,
    inout ig_metadata_t ig_meta,
    in ingress_intrinsic_metadata_t ig_intr_md,
    in ingress_intrinsic_metadata_from_parser_t ig_intr_md_from_prsr,
    inout ingress_intrinsic_metadata_for_deparser_t ig_intr_md_for_dprsr,
    inout ingress_intrinsic_metadata_for_tm_t ig_intr_md_for_tm){
	
	action miss(bit<3> drop_bits) {
		ig_intr_md_for_dprsr.drop_ctl = drop_bits;
	}

	action forward(PortId_t port){
		ig_intr_md_for_tm.ucast_egress_port = port;
	}

	action route_init_dummy_pkt(PortId_t port, QueueId_t qid){
		ig_intr_md_for_tm.ucast_egress_port = port;
		ig_intr_md_for_tm.qid = qid;
	}

	action multicast(MulticastGroupId_t grp_id, QueueId_t qid){
		ig_intr_md_for_tm.mcast_grp_a = grp_id;
		ig_intr_md_for_tm.qid = qid;
	}


	action drop(){
		ig_intr_md_for_dprsr.drop_ctl = 0x1;
	}
	action nop(){ }

	table l2_forward {
		key = {
			hdr.ethernet.dst_addr: exact;
		}

		actions = {
			forward;
			route_init_dummy_pkt;
			multicast;
			@defaultonly nop;
		}

		const default_action = nop();// miss(0x1);

	}

	// table toggle_pktgen {
	// 	key = {

	// 	}

	// 	actions = {
	// 		@defaultonly drop;
	// 		@defaultonly nop;
	// 	}

	// 	default_action = drop();
	// }

	Register<bit<32>,bit<1>>(1,0) reg_pktgen_cntr;
	RegisterAction<bit<32>,bit<1>,bit<3>>(reg_pktgen_cntr) decide_pktgen_drop = {
		void apply(inout bit<32> reg_val, out bit<3> rv){
			if(reg_val == 65536){
				rv = 0b001;
			}
			else{
				reg_val = reg_val + 1;
				rv = 0b000;
			}
		}
	};

	action check_pktgen_cntr_and_drop(){
		ig_intr_md_for_dprsr.drop_ctl = decide_pktgen_drop.execute(0);
	}

	table limit_pktgen_traffic{
		actions = {
			check_pktgen_cntr_and_drop;
			nop;
		}
		key = {	}
		size = 1;
		default_action = check_pktgen_cntr_and_drop;
	}

    action remove_pktgen_add_ether(){
        hdr.pktgen_timer.setInvalid();
        hdr.remaining_ethernet.setInvalid();

        hdr.ethernet.setValid();
        hdr.ethernet.dst_addr = RECEIVER_SW_ADDR; 
        hdr.ethernet.src_addr = ig_intr_md_from_prsr.global_tstamp; //SENDER_SW_ADDR; 
        hdr.ethernet.ether_type = ether_type_t.IPV4;
    }

	Register<seq_no_t,bit<8>>(MAX_PORTS,0) reg_leading_ack;
	action record_leading_ack(){ // set by courier/piggedbacked lack pkts
		reg_leading_ack.write(ig_intr_md.ingress_port[7:0], hdr.linkradar_lack.leading_ack);
	}
	action retrieve_leading_ack(){ // read by buffered pkts
		ig_meta.curr_leading_ack = reg_leading_ack.read(hdr.linkradar_buffered.dst_eg_port[7:0]);
	}

	Register<bit<8>,bit<8>>(MAX_PORTS,0) reg_leading_ack_era;
	action record_leading_ack_era(){ // set by courier/piggedbacked lack pkts
		reg_leading_ack_era.write(ig_intr_md.ingress_port[7:0], (bit<8>)hdr.linkradar_lack.era);
	}
	
	action retrieve_leading_ack_era(){ // read by buffered pkts
		ig_meta.curr_era = reg_leading_ack_era.read(hdr.linkradar_buffered.dst_eg_port[7:0]);
	}

	Register<bit<8>,bit<1>>(1,0) reg_debug_index;
	Register<bit<8>,bit<1>>(1,0) reg_debug_value;

	action record_debug_index(){
		reg_debug_index.write(0, hdr.linkradar_buffered.dst_eg_port[7:0]);
	}

	action record_debug_value(){
		reg_debug_value.write(0, (bit<8>)ig_meta.curr_era);
	}


	action decap_piggybacked_pkt(){
		hdr.linkradar_lack.setInvalid();
		hdr.ethernet.ether_type = ether_type_t.IPV4;
	}
	table drop_courier_pkt_or_decap_piggybacked_pkt{
		actions = {
			drop;
			decap_piggybacked_pkt;
			nop;
		}
		key = {
			hdr.linkradar_lack.is_piggy_backed: exact;
		}
		size = 2;
		const entries = {
			0: drop(); // courier pkt. drop it!
			1: decap_piggybacked_pkt(); // piggybacked pkt. decap it!
		}
	}

	Register<bit<32>,bit<1>>(1,0) reg_debug_counter;
	RegisterAction<bit<32>,bit<1>,bit<32>>(reg_debug_counter) 
	increment_debug_counter = {
		void apply(inout bit<32> reg_val, out bit<32> rv){
			reg_val = reg_val + 1;
		}
	};
	action debug_count(){
		increment_debug_counter.execute(0);
	}

	// ####### HOLES TRACKING REGISTERS - START #######
	Register<bit<1>,seq_no_t>(MAX_SEQ_NUMBERS,0) reg_holes_1;
	action set_holes_1(){ // NOTE: hole_1 is special. Always the 1st lost seq #
		reg_holes_1.write(hdr.linkradar_loss_notification.first_lost_seq_no, 1);
	}
	RegisterAction<bit<1>,seq_no_t,bit<1>>(reg_holes_1) read_reset_reg_holes_1 = {
		void apply(inout bit<1> reg_val, out bit<1> rv){
			rv = reg_val;
			reg_val = 0;
		}
	};
	action check_reset_holes_1(){
		ig_meta.is_missing_hole_1 = read_reset_reg_holes_1.execute(hdr.linkradar_data.seq_no);
	}

	Register<bit<1>,seq_no_t>(MAX_SEQ_NUMBERS,0) reg_holes_2;
	action set_holes_2(){ 
		reg_holes_2.write(ig_meta.holes_2_seq_no, 1);
	}
	RegisterAction<bit<1>,seq_no_t,bit<1>>(reg_holes_2) read_reset_reg_holes_2 = {
		void apply(inout bit<1> reg_val, out bit<1> rv){
			rv = reg_val;
			reg_val = 0;
		}
	};
	action check_reset_holes_2(){
		ig_meta.is_missing_hole_2 = read_reset_reg_holes_2.execute(hdr.linkradar_data.seq_no);
	}

	Register<bit<1>,seq_no_t>(MAX_SEQ_NUMBERS,0) reg_holes_3;
	action set_holes_3(){ 
		reg_holes_3.write(ig_meta.holes_3_seq_no, 1);
	}
	RegisterAction<bit<1>,seq_no_t,bit<1>>(reg_holes_3) read_reset_reg_holes_3 = {
		void apply(inout bit<1> reg_val, out bit<1> rv){
			rv = reg_val;
			reg_val = 0;
		}
	};
	action check_reset_holes_3(){
		ig_meta.is_missing_hole_3 = read_reset_reg_holes_3.execute(hdr.linkradar_data.seq_no);
	}

	Register<bit<1>,seq_no_t>(MAX_SEQ_NUMBERS,0) reg_holes_4;
	action set_holes_4(){
		reg_holes_4.write(ig_meta.holes_4_seq_no, 1);
	}
	RegisterAction<bit<1>,seq_no_t,bit<1>>(reg_holes_4) read_reset_reg_holes_4 = {
		void apply(inout bit<1> reg_val, out bit<1> rv){
			rv = reg_val;
			reg_val = 0;
		}
	};
	action check_reset_holes_4(){
		ig_meta.is_missing_hole_4 = read_reset_reg_holes_4.execute(hdr.linkradar_data.seq_no);
	}

	Register<bit<1>,seq_no_t>(MAX_SEQ_NUMBERS,0) reg_holes_5;
	action set_holes_5(){
		reg_holes_5.write(ig_meta.holes_5_seq_no, 1);
	}
	RegisterAction<bit<1>,seq_no_t,bit<1>>(reg_holes_5) read_reset_reg_holes_5 = {
		void apply(inout bit<1> reg_val, out bit<1> rv){
			rv = reg_val;
			reg_val = 0;
		}
	};
	action check_reset_holes_5(){
		ig_meta.is_missing_hole_5 = read_reset_reg_holes_5.execute(hdr.linkradar_data.seq_no);
	}

	// ####### HOLES TRACKING REGISTERS - END #######
	
	action add_bridged_metadata(){
		hdr.bridged_meta.setValid();
        hdr.bridged_meta.type = INTERNAL_HDR_TYPE_BRIDGED_META;
        hdr.bridged_meta.info = 0;
	}

	DirectCounter<bit<64>>(CounterType_t.PACKETS) era_correction_cntr;

	action adjust_seq_nos(){
		ig_meta.buffered_seq_no = ig_meta.buffered_seq_no - SEQ_NUMBERS_HALF_RANGE;
		ig_meta.curr_leading_ack = ig_meta.curr_leading_ack - SEQ_NUMBERS_HALF_RANGE;
		era_correction_cntr.count();
	}
	
	action nop_era_correction(){
		era_correction_cntr.count();
	}
	table era_correction{
		actions = {
			adjust_seq_nos;
			nop_era_correction;
		}
		key = {
			hdr.linkradar_data.era: exact;
			ig_meta.curr_era: exact;
		}
		size = 4;
		counters = era_correction_cntr;

		const entries = {
			(0,0): nop_era_correction();
			(1,1): nop_era_correction();
			(1,0): adjust_seq_nos();
			(0,1): adjust_seq_nos();
		}
		
	}
	
	Register<bit<32>, bit<1>>(1,0) reg_buffered_dropped_records_idx;
	RegisterAction<bit<32>, bit<1>, bit<32>>(reg_buffered_dropped_records_idx) read_increment_buffered_dropped_records_idx = {
		void apply(inout bit<32> reg_val, out bit<32> rv){
			rv = reg_val;
			
			if(reg_val < MAX_BUFFERED_DROPPED_RECORDS){ // saturating increment
				reg_val = reg_val + 1; 
			}
		}
	};

	action get_buffered_dropped_records_idx(){
		ig_meta.buffered_dropped_records_idx = read_increment_buffered_dropped_records_idx.execute(0);
	}

	Register<buffered_dropped_record_t, bit<32>>(MAX_BUFFERED_DROPPED_RECORDS, {0,0}) reg_buffered_dropped_records;
	RegisterAction<buffered_dropped_record_t, bit<32>, bit<32>>(reg_buffered_dropped_records) write_buffered_dropped_record = {
		void apply(inout buffered_dropped_record_t reg_val, out bit<32> rv){
			reg_val.curr_lack = ig_meta.curr_leading_ack;
			reg_val.buffered_seq_no = ig_meta.buffered_seq_no;
		}
	};
	
	action record_buffered_dropped_pkt(){
		write_buffered_dropped_record.execute(ig_meta.buffered_dropped_records_idx);
	}


	DirectCounter<bit<64>>(CounterType_t.PACKETS) decide_retx_or_drop_cntr;

	action set_buffered_pkt_retx(){
		ig_meta.retx = 1;
		decide_retx_or_drop_cntr.count();
	}

	action drop_buffered_pkt(){
		ig_meta.retx = 0;
		drop();
		decide_retx_or_drop_cntr.count();
	}

	table decide_retx_or_drop{
		actions = {
			set_buffered_pkt_retx;
			drop_buffered_pkt;
			@defaultonly nop;
		}
		key = {
			ig_meta.is_missing_hole_1: ternary;
			ig_meta.is_missing_hole_2: ternary;
			ig_meta.is_missing_hole_3: ternary;
			ig_meta.is_missing_hole_4: ternary;
			ig_meta.is_missing_hole_5: ternary;
		}
		size = 6;
		default_action = nop();
		counters = decide_retx_or_drop_cntr;
		const entries = {
			// 1 : set_buffered_pkt_retx();
			// 0 : drop_buffered_pkt();
			(1,_,_,_,_): set_buffered_pkt_retx();
			(_,1,_,_,_): set_buffered_pkt_retx();
			(_,_,1,_,_): set_buffered_pkt_retx();
			(_,_,_,1,_): set_buffered_pkt_retx();
			(_,_,_,_,1): set_buffered_pkt_retx();
			(0,0,0,0,0): drop_buffered_pkt();
		}
	}

	DirectCounter<bit<64>>(CounterType_t.PACKETS) retx_mcast_buffered_pkt_cntr;

	action do_retx_buffered_pkt_ucast(){
		// set the routing
		ig_intr_md_for_tm.ucast_egress_port = hdr.linkradar_buffered.dst_eg_port;
		ig_intr_md_for_tm.qid = RETX_QID;

		// remove the lr_buffered hdr and set reTx flag in lr_data hdr
		hdr.linkradar_buffered.setInvalid();
		hdr.linkradar_data.reTx = 1;

		// by pass the egress processing
		ig_intr_md_for_tm.bypass_egress = 1;

		retx_mcast_buffered_pkt_cntr.count();
	}

	action do_retx_buffered_pkt_mcast(MulticastGroupId_t grp_id){
		// set the routing
		ig_intr_md_for_tm.mcast_grp_a = grp_id;
		ig_intr_md_for_tm.qid = RETX_QID;

		// remove the lr_buffered hdr and set reTx flag in lr_data hdr
		hdr.linkradar_buffered.setInvalid();
		hdr.linkradar_data.reTx = 1;

		// by pass the egress processing
		ig_intr_md_for_tm.bypass_egress = 1;

		retx_mcast_buffered_pkt_cntr.count();
	}
	
	table retx_mcast_buffered_pkt{
		actions = {
			do_retx_buffered_pkt_ucast;
			do_retx_buffered_pkt_mcast;
			@defaultonly nop;
		}
		key = {
			hdr.linkradar_buffered.dst_eg_port: exact;
		}
		size = MAX_PROTECTED_PORTS;
		default_action = nop();
		counters = retx_mcast_buffered_pkt_cntr;
	}

	action get_min_of_seq_leading_ack(){
		ig_meta.min_val = min(ig_meta.buffered_seq_no, ig_meta.curr_leading_ack);
	}

	Register<bit<1>,bit<16>>(MAX_SEQ_NUMBERS) reg_circulating_era_0;
	Register<bit<1>,bit<16>>(MAX_SEQ_NUMBERS) reg_circulating_era_1;

	action record_pkt_in_circulating_era_0(){
		reg_circulating_era_0.write(hdr.linkradar_data.seq_no ,1);
	}
	action record_pkt_in_circulating_era_1(){
		reg_circulating_era_1.write(hdr.linkradar_data.seq_no ,1);
	}

	Register<bit<32>, bit<1>>(1,0) reg_lack_hole_records_idx;
	RegisterAction<bit<32>, bit<1>, bit<32>>(reg_lack_hole_records_idx) read_increment_lack_hole_records_idx = {
		void apply(inout bit<32> reg_val, out bit<32> rv){
			rv = reg_val;
			
			if(reg_val < MAX_LACK_HOLE_RECORDS){ // saturating increment
				reg_val = reg_val + 1; 
			}
		}
	};
	action get_lack_hole_records_idx(){
		ig_meta.lack_hole_records_idx = read_increment_lack_hole_records_idx.execute(0);
	}

	Register<lack_hole_records_t,bit<32>>(MAX_LACK_HOLE_RECORDS,{0,0}) reg_lack_hole_records;
	RegisterAction<lack_hole_records_t,bit<32>, bit<32>>(reg_lack_hole_records) write_both_lack_and_hole = {
		void apply(inout lack_hole_records_t reg_val, out bit<32> rv){
			reg_val.lack = hdr.linkradar_lack.leading_ack;
			reg_val.first_lost_seq_no = hdr.linkradar_loss_notification.first_lost_seq_no;
		}
	};
	RegisterAction<lack_hole_records_t,bit<32>, bit<32>>(reg_lack_hole_records) write_just_lack = {
		void apply(inout lack_hole_records_t reg_val, out bit<32> rv){
			reg_val.lack = hdr.linkradar_lack.leading_ack;
		}
	};
	action record_both_lack_and_hole(){
		write_both_lack_and_hole.execute(ig_meta.lack_hole_records_idx);
	}
	action record_just_lack(){
		write_just_lack.execute(ig_meta.lack_hole_records_idx);
	}

	action bypass_egress(){
		ig_intr_md_for_tm.bypass_egress = 1;
	}

	action prep_multi_hole_seq_nos(){
		ig_meta.holes_2_seq_no = ig_meta.first_lost_seq_no_copy + 1;
		ig_meta.holes_3_seq_no = ig_meta.first_lost_seq_no_copy + 2;
		ig_meta.holes_4_seq_no = ig_meta.first_lost_seq_no_copy + 3;
		ig_meta.holes_5_seq_no = ig_meta.first_lost_seq_no_copy + 4;
	}

	apply {

		if(hdr.pktgen_timer.isValid()){ // Pktgen pkt received on dev_port 68. 
			// Forward it out on wire.
            remove_pktgen_add_ether();
			// toggle_pktgen.apply(); // to help control pktgen traffic via bfrt_python 
			#if DEBUG
			// check_pktgen_cntr_and_drop();
			limit_pktgen_traffic.apply();
			#endif
		}
		
		if(hdr.linkradar_lack.isValid()){ // leading ACK [+ loss notification] from Rx
			record_leading_ack();		  // OR NORMAL pkts piggybacked with leading ACK
			record_leading_ack_era();
			// record_leading_ack_era.apply();
			drop_courier_pkt_or_decap_piggybacked_pkt.apply();

			#if DEBUG
			get_lack_hole_records_idx();
			#endif
			if(hdr.linkradar_loss_notification.isValid()){
				prep_multi_hole_seq_nos();
				set_holes_1();
				if(hdr.linkradar_loss_notification.hole_size >= 2){
					set_holes_2();
				}
				if(hdr.linkradar_loss_notification.hole_size >= 3){
					set_holes_3();
				}
				if(hdr.linkradar_loss_notification.hole_size >= 4){
					set_holes_4();
				}
				if(hdr.linkradar_loss_notification.hole_size >= 5){
					set_holes_5();
				}
				#if DEBUG
				record_both_lack_and_hole();
				#endif
			}
			else{
				#if DEBUG
				record_just_lack();
				#endif
			}
		}
		else if (hdr.linkradar_buffered.isValid()){ // buffered packets
			// for bufferred pkts, need to read and compare the lack + era

			// step 1: read leading_ack, era and hole bits for the seq_no
			record_debug_index();
			retrieve_leading_ack(); // fills ig_meta.curr_leading_ack
			retrieve_leading_ack_era(); // fills ig_meta.curr_era
			record_debug_value();

			// step 2: compare the era and do correction if needed
			era_correction.apply();
			
			// step 3: compare buffered pkt's seq with leading_ack
			get_min_of_seq_leading_ack();
			if(ig_meta.min_val == ig_meta.buffered_seq_no){ 
				// above 2 lines express: ig_meta.buffered_seq_no <= ig_meta.curr_leading_ack
				// either reTx or drop

				check_reset_holes_1(); // fills ig_meta.is_missing_hole_1
				check_reset_holes_2(); // fills ig_meta.is_missing_hole_2
				check_reset_holes_3(); // fills ig_meta.is_missing_hole_3
				check_reset_holes_4(); // fills ig_meta.is_missing_hole_4
				check_reset_holes_5(); // fills ig_meta.is_missing_hole_5

				decide_retx_or_drop.apply(); // sets ig_meta.retx OR sets drop_ctl

				if(ig_meta.retx == 1){ // decided to reTx
					retx_mcast_buffered_pkt.apply();
				}
				else{ // decided to drop
					#if DEBUG
					get_buffered_dropped_records_idx();
					record_buffered_dropped_pkt();
					#endif
				}
			}
			else { // continue to recirculate
				// TODO: add a recirculation port lookup table (for multiple links protection)
				ig_intr_md_for_tm.ucast_egress_port = RECIRC_LPBK_PORT;
				bypass_egress();

				#if DEBUG
				if(hdr.linkradar_data.era == 0){
					record_pkt_in_circulating_era_0();
				}
				else if(hdr.linkradar_data.era == 1){
					record_pkt_in_circulating_era_1();
				}
				#endif

				debug_count();
			}
			
		} // end of hdr.linkradar_buffered.isValid()
		
		// BUG fix: piggybacked reverse direction pkt weren't forwarded!
		// BUG fix: with mcast reTx, ucast still happening. So 3 copies being sent!
		//          a mcast reTx pkt already has invalid lr_buffered hdr
		if(!hdr.linkradar_buffered.isValid() && ig_meta.retx != 1){ 
			// (decapped) normal, pktgen, init_dummy pkts but NOT decapped reTx pkts
			// basically all pkts except buffered ones rely on the l2_forward table
			// buffered pkts have their own retx_mcast_buffered_pkt table for forwarding
			l2_forward.apply();  
		}

		if(ig_intr_md_for_tm.bypass_egress == 0){
			add_bridged_metadata(); // every pkt going to egress should hv the INTERNAL_HEADER
		}

	} // end of the apply block

}  // End of SwitchIngressControl

// BUG fix. ECN marking overriding blocking_mode and rx_mode bits
@pa_no_overlay("egress","hdr.ipv4.ecn")
control SwitchEgress(
    inout header_t hdr,
    inout eg_metadata_t eg_meta,
    in egress_intrinsic_metadata_t eg_intr_md,
    in egress_intrinsic_metadata_from_parser_t eg_intr_md_from_prsr,
    inout egress_intrinsic_metadata_for_deparser_t eg_intr_md_for_dprsr,
    inout egress_intrinsic_metadata_for_output_port_t eg_intr_md_for_oport){
	
	Counter<bit<64>,debug_counter_idx_t>(DEBUG_COUNTER_SIZE,CounterType_t.PACKETS_AND_BYTES) eg_debug_counter;

	Counter<bit<64>,debug_counter_idx_t>(DEBUG_COUNTER_SIZE,CounterType_t.PACKETS_AND_BYTES) eg_debug_counter2;

	action nop(){ }

	action drop() {
		eg_intr_md_for_dprsr.drop_ctl = 3w1;
	}

	Register<bit<32>,bit<1>>(1,0) reg_debug_counter;
	RegisterAction<bit<32>,bit<1>,bit<32>>(reg_debug_counter) 
	increment_debug_counter = {
		void apply(inout bit<32> reg_val, out bit<32> rv){
			reg_val = reg_val + 1;
		}
	};
	action debug_count(){
		increment_debug_counter.execute(0);
	}


	Register<seq_no_t,bit<8>>(MAX_PORTS,0) reg_seq_no;

	RegisterAction<seq_no_t,bit<8>,seq_no_t>(reg_seq_no) get_next_seq_no = {
		void apply(inout seq_no_t reg_val, out seq_no_t rv){
			rv = reg_val;
			reg_val = reg_val + 1;
		}
	};

	RegisterAction<seq_no_t,bit<8>,seq_no_t>(reg_seq_no) get_curr_seq_no = {
		void apply(inout seq_no_t reg_val, out seq_no_t rv){
			rv = reg_val;
		}
	};

	Register<bit<8>,bit<8>>(MAX_PORTS,0) reg_era;

	RegisterAction<bit<8>,bit<8>,bit<8>>(reg_era) do_get_update_era = {
		void apply(inout bit<8> reg_val, out bit<8> rv){
			rv = reg_val;		
			reg_val = ~reg_val; // toggle 0 and 1
		}
	};

	RegisterAction<bit<8>,bit<8>,bit<8>>(reg_era) do_get_era = {
		void apply(inout bit<8> reg_val, out bit<8> rv){
			rv = reg_val;
		}
	};

	Register<bit<8>,bit<8>>(MAX_PORTS,0) reg_dummy_pkt_notify_count;
	RegisterAction<bit<8>,bit<8>,bit<1>>(reg_dummy_pkt_notify_count) do_check_if_dummy_pkt_pending = {
		void apply(inout bit<8> reg_val, out bit<1> rv){
			bit<8> count;
			count = reg_val;
			if(count > 0){
				rv = 1;
				reg_val = reg_val - 1;
			}
			else{ // count is zero
				rv = 0;
				// reg_val = 0;
			}
		}
	};
	action check_if_dummy_pkt_pending(){
		eg_meta.is_dummy_pkt_pending = do_check_if_dummy_pkt_pending.execute(eg_intr_md.egress_port[7:0]);
	}
	action set_dummy_pkt_notify_max_count(){
		reg_dummy_pkt_notify_count.write(eg_intr_md.egress_port[7:0], eg_meta.dummy_pkt_notify_max_count);
	}

	action protect(bit<8> dummy_pkt_max_count, bit<1> blocking_mode){ // encaps with seq no
		hdr.ethernet.ether_type = ether_type_t.LINKRADAR;
		hdr.linkradar_data.setValid();
		
		hdr.linkradar_data.type = LINKRADAR_HDR_TYPE_DATA;
		hdr.linkradar_data._pad = 0;
		hdr.linkradar_data.era = 0; // for now
		hdr.linkradar_data.reTx = 0;
		hdr.linkradar_data.dummy = 0;
		hdr.linkradar_data.blocking_mode = blocking_mode;
		hdr.linkradar_data.rx_buffered = 0; 
		
		hdr.linkradar_data.seq_no = get_next_seq_no.execute(eg_intr_md.egress_port[7:0]);

		eg_meta.dummy_pkt_notify_max_count = dummy_pkt_max_count;

		#if MEASURE_RETX_LATENCY
		// Initial plan: use as hash pkt signature
		// Not used currently: can give some idea abt inter-loss time gaps
		hdr.ethernet.src_addr = eg_intr_md_from_prsr.global_tstamp;
		#endif
	}

	action action_get_update_era(){
		hdr.linkradar_data.era = (bit<1>)do_get_update_era.execute(eg_intr_md.egress_port[7:0]);
	}

	// workaround for SDE 9.9.0 bug: 
	// multiple instances of actions/tables related to reg_era in 2 diff stages!
	// SDE 9.10.0 allocates this to stage 2. But SDE 9.9.0 needs stage 3 somehow.
	// @stage(3)
	table get_update_era{
		actions = {
			action_get_update_era;
		}
		key = {
			
		}
		size = 1;
		const default_action = action_get_update_era();
	}

	action action_get_era(){
		hdr.linkradar_data.era = (bit<1>)do_get_era.execute(eg_intr_md.egress_port[7:0]);
	}

	// workaround for SDE 9.9.0 bug: 
	// multiple instances of actions/tables related to reg_era in 2 diff stages!
	// SDE 9.10.0 allocates this to stage 2. But SDE 9.9.0 needs stage 3 somehow.
	// @stage(3)
	table get_era{
		actions = {
			action_get_era;
		}
		key = {
		}
		size = 1;
		const default_action = action_get_era();
	}

	action add_curr_seq_no_to_dummy(){
		hdr.linkradar_data.seq_no = get_curr_seq_no.execute(eg_intr_md.egress_port[7:0]);
	}

	action action_add_curr_era_to_dummy(){
		action_get_era();
	}

	// workaround for SDE 9.9.0 bug: 
	// multiple instances of actions/tables related to reg_era in 2 diff stages!
	// SDE 9.10.0 allocates this to stage 2. But SDE 9.9.0 needs stage 3 somehow.
	// @stage(3)
	table add_curr_era_to_dummy{
		actions = {
			action_add_curr_era_to_dummy;
		}
		key = {
			
		}
		size = 1;
		const default_action = action_add_curr_era_to_dummy();
	}

	action mark_for_corruption_emulation(bit<8> seqno_lookup_idx){
		eg_meta.emulate_corruption = 1;
		// eg_meta.corruption_seq_no_idx = seqno_lookup_idx;
	}
	table decide_to_emulate_corruption {
		key = {
			eg_intr_md.egress_port[7:0]: exact;
		}
		actions = {
			mark_for_corruption_emulation;
			@defaultonly nop;
		}
		const default_action = nop();
		size = 256;
	}
		
	Register<seq_no_t,bit<8>>(MAX_PORTS,0) reg_corruption_seq_no;

	RegisterAction<seq_no_t,bit<8>,seq_no_t>(reg_corruption_seq_no) get_incr_corruption_seq_no = {
		void apply(inout seq_no_t reg_val, out seq_no_t rv){
			rv = reg_val;
			reg_val = reg_val + 1;
		}
	};

	action get_corruption_seq_no(){
		eg_meta.corruption_seq_no = get_incr_corruption_seq_no.execute(eg_intr_md.egress_port[7:0]);
	}	
	
	Register<bit<32>,bit<1>>(1, 0) reg_emulated_corruption_counter;
	RegisterAction<bit<32>,bit<1>,bit<32>>(reg_emulated_corruption_counter) increment_emulated_corruption_counter = {
		void apply(inout bit<32> reg_val, out bit<32> rv){
			reg_val = reg_val + 1;
		}
	};

	action count_emulated_corruption(){
		increment_emulated_corruption_counter.execute(0);
	}

	action corrupt(){
		eg_intr_md_for_dprsr.drop_ctl = 3w1;
		count_emulated_corruption();
	}

	table emulate_corruption {
		key = {
			eg_meta.corruption_seq_no: exact;
		}
		actions = {
			corrupt;
			@defaultonly nop;
		}
		size = MAX_SEQ_NUMBERS;
		const default_action = nop();
	}

    table link_protect{
        actions = {
            protect;
            @defaultonly nop;
        }
        key = {
            eg_intr_md.egress_port: exact;
        }
        size = MAX_PROTECTED_PORTS;
        const default_action = nop();
    }

	// Register to record eg buffered pkt stats
	// index 0: number of pkts sent for eg mirroring
	// index 1: number of pkts successfully eg mirrored
	Register<bit<32>, bit<2>>(4,0) reg_buffered_pkts_eg_stats;
	RegisterAction<bit<32>, bit<2>, bit<32>>(reg_buffered_pkts_eg_stats) increment_eg_buffered_stats = {
		void apply(inout bit<32> reg_val, out bit<32> rv){
			reg_val = reg_val + 1;
		}
	};
	action record_eg_mirror_sent_pkts(){
		increment_eg_buffered_stats.execute(0);
		// eg_debug_counter2.count(0);
	}
	// Action not being used anymore
	action record_eg_mirror_success_pkts(){
		// increment_eg_buffered_stats.execute(1);
		// eg_debug_counter2.count(1);
	}

	action copy_for_buffering(MirrorId_t mirror_session){
		// signal the mirroring
		eg_intr_md_for_dprsr.mirror_type = EG_MIRROR_BUFFERED_PKT;

		// set mirror session
		eg_meta.mirror_session = mirror_session;

		// set up internal hdr
		eg_meta.internal_hdr_type = INTERNAL_HDR_TYPE_EG_MIRROR;
    	eg_meta.internal_hdr_info = (bit<4>)EG_MIRROR_BUFFERED_PKT;

		// fill data into the internal hdr
		eg_meta.emulated_dropped = 0;
		eg_meta.dst_eg_port = eg_intr_md.egress_port;

		#if DEBUG
		record_eg_mirror_sent_pkts();
		// eg_debug_counter2.count(0);
		#endif
	}

	table copy_pkt_for_buffering{
		actions = {
			copy_for_buffering;
			nop;
		}
		key = {
			eg_intr_md.egress_port: exact;
		}
		size = MAX_PROTECTED_PORTS;
		const default_action = nop();
	}

	action add_linkradar_buffered_hdr(){
		hdr.linkradar_buffered.setValid();
		hdr.linkradar_buffered.type = LINKRADAR_HDR_TYPE_TX_BUFFERED;
	}

	action fill_data_linkradar_buffered_hdr(){
		hdr.linkradar_buffered.dst_eg_port = eg_meta.eg_mirror_buffered_pkt.dst_eg_port;
	}

	action do_mirror_dummy_pkt(MirrorId_t mirror_session){
		// prepare the internal header for EG_MIRROR
		eg_meta.internal_hdr_type = INTERNAL_HDR_TYPE_EG_MIRROR;
    	eg_meta.internal_hdr_info = (bit<4>)EG_MIRROR_DUMMY_PKT;

		// set for mirroring
		eg_intr_md_for_dprsr.mirror_type = EG_MIRROR_DUMMY_PKT;

		// set the mirror session
		eg_meta.mirror_session = mirror_session; 
	}

	table mirror_dummy_pkt{
		actions = {
			do_mirror_dummy_pkt;
			nop;
		}
		key = {
			eg_intr_md.egress_port: exact;
		}
		size = MAX_PROTECTED_PORTS;
		default_action = nop();
	}

	/* action mirror_to_report_affected_flow(bit<4> subtype){
		// setup mirroring
		eg_intr_md_for_dprsr.mirror_type = EG_MIRROR_AFFECTED_FLOW; // deparser hdr selection
		eg_meta.mirror_session = MIRROR_SESSION_AFFECTED_FLOWS;
		// setup the internal hdr
		eg_meta.internal_hdr_type = INTERNAL_HDR_TYPE_EG_MIRROR_AFFECTED_FLOW;
    	eg_meta.internal_hdr_info = subtype;
	} */

	action decap_buffered_pkt_hdrs(){
		hdr.linkradar_buffered.setInvalid();
		hdr.linkradar_data.setInvalid();
		hdr.ethernet.ether_type = ether_type_t.IPV4;
	}

	action set_eg_meta_emulated_drop(){
		eg_meta.emulated_dropped = 1;
	}

	// ##### DCTCP ECN Marking #####
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
		eg_meta.mark_ecn_codepoint = cmp_ecn_marking_threshold.execute(0);
	}

	action mark_ecn_ce_codepoint(){
		hdr.ipv4.ecn = 0b11;
	}
	// ##### DCTCP ECN Marking (end) #####

	// ##### DCQCN ECN Marking #####
	action dcqcn_mark_probability(bit<8> value) {
		eg_meta.dcqcn_prob_output = value;
	}

	table dcqcn_get_ecn_probability {
		key = {
			eg_intr_md.deq_qdepth : range; // 19 bits
		}
		actions = {
			dcqcn_mark_probability;
		}
		const default_action = dcqcn_mark_probability(0); // default: no ecn mark
		size = 1024;
	}

	Random<bit<8>>() random;  // random seed for sampling
	action dcqcn_get_random_number(){
		eg_meta.dcqcn_random_number = random.get();
	}

	action dcqcn_check_ecn_marking() {
		eg_meta.mark_ecn_codepoint = 1;
	}
	
	table dcqcn_compare_probability {
		key = {
			eg_meta.dcqcn_prob_output : exact;
			eg_meta.dcqcn_random_number : exact;
		}
		actions = {
			dcqcn_check_ecn_marking;
			@defaultonly nop;
		}
		const default_action = nop();
		size = 8192;
	}


	// ##### DCQCN ECN Marking (end) #####

	apply{
		if(!hdr.linkradar_data.isValid()){ // normal packet OR unprotected affected flow mirrored pkt
			// #### ECN Marking  ######
			if(hdr.ipv4.ecn == 0b01 || hdr.ipv4.ecn == 0b10){
				if(eg_meta.is_roce_v2 == 1){   // RoCEv2 Pkt
					/* DCQCN (RED-like marking) */
					dcqcn_get_ecn_probability.apply(); // get probability to ecn-mark
					dcqcn_get_random_number(); // get random number for sampling
					dcqcn_compare_probability.apply(); // fills eg_meta.mark_ecn_codepoint
				}
				else{  // use DCTCP-like marking
					check_ecn_marking_threshold(); // fills eg_meta.mark_ecn_codepoint
				}

				if(eg_meta.mark_ecn_codepoint == 1){
					mark_ecn_ce_codepoint();
				}
			}
			// #### ECN Marking (end) ######
			
			link_protect.apply(); // encap with linkradar. sets eg_meta.dummy_pkt_notify_max_count
			
			if(hdr.linkradar_data.isValid()){ 
				// copy pkt for buffering only if it is protected
				copy_pkt_for_buffering.apply();
				set_dummy_pkt_notify_max_count();

				// do era adjustment if the pkt is protected
				if(hdr.linkradar_data.seq_no == MAX_SEQ_NO){ // 65535 
					get_update_era.apply(); // fills hdr.linkradar_data.era and toggles reg_era
				}
				else{
					get_era.apply(); // fills hdr.linkradar_data.era
				}

				if(hdr.linkradar_data.blocking_mode == 0){
					eg_debug_counter.count(0);
				}
				else{
					eg_debug_counter.count(1);
				}
			}

			#if DEBUG
			decide_to_emulate_corruption.apply(); // sets eg_meta.emulate_corruption
			get_corruption_seq_no(); // like a simple eg_counter
			if(eg_meta.emulate_corruption == 1){
				emulate_corruption.apply(); // emulate corruption pkt drops
			}

			//#######  AFFECTED FLOWS TELEMETRY #######
			// if(eg_intr_md_for_dprsr.drop_ctl == 1){ // packet being dropped
			// 	if(hdr.linkradar_data.isValid()){ // protected pkt
			// 		set_eg_meta_emulated_drop();
			// 	}
			// 	else{ // unprotected packet
			// 		mirror_to_report_affected_flow(EG_MIRROR_AFFECTED_FLOW_UNPROTECTED);
			// 	}
			// }
			#endif
		}
		else{ // hdr.linkradar_data.isValid() 
			if(eg_meta.eg_mirror_buffered_pkt.isValid()){ // eg mirrored pkt for buffering
				// add lr_buffered hdr and allow the pkt to go to the recirc port
				add_linkradar_buffered_hdr();
				fill_data_linkradar_buffered_hdr();

				#if DEBUG
				// record_eg_mirror_success_pkts();
				eg_debug_counter2.count(0);
				// if(eg_meta.eg_mirror_buffered_pkt.emulated_dropped == 1){
				// 	mirror_to_report_affected_flow(EG_MIRROR_AFFECTED_FLOW_PROTECTED);
				// }
				#endif
			}
			// else if(hdr.linkradar_buffered.isValid() && !eg_meta.eg_mirror_affected_flow.isValid()){
			// 	// recirculating buffered pkt and NOT its mirrored copy for affected flow reporting
				
			// }
			else if(hdr.linkradar_data.dummy == 1){ // dummy pkt
				debug_count();
				add_curr_seq_no_to_dummy();
				add_curr_era_to_dummy.apply();
				mirror_dummy_pkt.apply(); // need to mirror in any case

				check_if_dummy_pkt_pending(); // sets eg_meta.is_dummy_pkt_pending

				if(eg_meta.is_dummy_pkt_pending == 0){ // drop if not pending
					drop();
				}
			}
			/* else if(eg_meta.eg_mirror_affected_flow.isValid()){ // affected flow mirrored pkt
				// if(hdr.linkradar_buffered.isValid()){  // affected flow protected
				decap_buffered_pkt_hdrs();
				// }
				// else{ // affected flow unprotected
				// 	// do nothing
				// }
			} */
		} // end of else i.e. hdr.linkradar_data.isValid()

		// remove bridged_meta before sending out on wire
		hdr.bridged_meta.setInvalid();
	}

} // End of SwitchEgress


Pipeline(SwitchIngressParser(),
		 SwitchIngress(),
		 SwitchIngressDeparser(),
		 SwitchEgressParser(),
		 SwitchEgress(),
		 SwitchEgressDeparser()
		 ) pipe;

Switch(pipe) main;

