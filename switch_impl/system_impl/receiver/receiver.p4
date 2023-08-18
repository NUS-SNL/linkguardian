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

#ifndef MEASURE_PFC_DELAYS
#define MEASURE_PFC_DELAYS 0
#endif

#ifndef MEASURE_BUFFER_DRAIN_RATE
#define MEASURE_BUFFER_DRAIN_RATE 0
#endif


#include "includes/headers.p4"
#include "includes/parser.p4"

#ifndef DEBUG
#define DEBUG 1
#endif


// #ifndef TIMEOUT_VAL_100NS
// #error Please specify -DTIMEOUT_VAL_100NS to the p4_build.sh script
// #endif

#ifndef TIMEOUT_VAL_100NS
#define TIMEOUT_VAL_100NS 70 // 135 for 10G. 75 for 25G. Orig 70 for 100G.
#endif

#define INFO_DEV_PORT_LUMOS_ENS3F0 132
#define DEBUG_COUNTER_IDX_WIDTH 4
#define DEBUG_COUNTER_SIZE 1<<DEBUG_COUNTER_IDX_WIDTH
typedef bit<DEBUG_COUNTER_IDX_WIDTH> debug_counter_idx_t;

const int RECEIVER_SW_ADDR = 0xAABBCCDDEEFF;
const int RECEIVER_SW_ADDR_HI_16 = 0xAABB;
const int SENDER_SW_ADDR = 0xAAAABBBBCCCC;
const int RECIRC_PORT_PIPE_0 = 20;
const int RECIRC_PORT_RX_BUFFER_QID = 0;

const int LOSS_NOTIFICATION_QID = 2;

const int MAX_PKT_RECORDS = 100000;
const int MAX_PKT_IPG_RECORDS = 70000;
#if MEASURE_PFC_DELAYS
const int MAX_PFC_REQ_RECORDS = 70000;
#else
const int MAX_PFC_REQ_RECORDS = 10000; // used for PFC debugging
#endif
const int MAX_QDEPTH_RECORDS = 70000;
const int MAX_POSSIBLE_IPG_NS = 2000; // max: 142ns @100G (measure) | 2000ns @10G (estimated)

const int AFFECTED_FLOWS_DEV_PORT = INFO_DEV_PORT_LUMOS_ENS3F0;

const int IG_PORT_WITH_BLOCKING_MODE_TIMEOUT = 36;

const int PAUSE_FRAME_MCAST_RID = 9999;
const int PAUSE_PFC_ETHER_DST_ADDR = 0x0180c2000001;
const int PAUSE_PFC_ETHER_SRC_ADDR = 0x000000000000;
const int PAUSE_OP_CODE = 0x0001;
const int PFC_OP_CODE = 0x0101;
const int MIRROR_SESSION_EG_PFC = 500;
const int MAX_PFC_QUANTA = 65535;
const int PFC_GEN_REQ_DROP = 0;
const int PFC_GEN_REQ_PAUSE = 1;
const int PFC_GEN_REQ_RESUME = 2;

#if MEASURE_RETX_LATENCY
const int RETX_LATENCY_SERVER_EG_PORT = 28;
#endif

control SwitchIngress(
    inout header_t hdr,
    inout ig_metadata_t ig_meta,
    in ingress_intrinsic_metadata_t ig_intr_md,
    in ingress_intrinsic_metadata_from_parser_t ig_intr_md_from_prsr,
    inout ingress_intrinsic_metadata_for_deparser_t ig_intr_md_for_dprsr,
    inout ingress_intrinsic_metadata_for_tm_t ig_intr_md_for_tm){

	Counter<bit<64>,debug_counter_idx_t>(DEBUG_COUNTER_SIZE,CounterType_t.PACKETS_AND_BYTES) ig_debug_counter;
	Counter<bit<64>,debug_counter_idx_t>(DEBUG_COUNTER_SIZE,CounterType_t.PACKETS_AND_BYTES) ig_debug_counter2;
	
	action nop(){ }
	action drop(){
		ig_intr_md_for_dprsr.drop_ctl = 0x1;
	}
	action forward(PortId_t port){
		ig_intr_md_for_tm.ucast_egress_port = port;
	}

	action route_init_courier_pkt(PortId_t port, QueueId_t qid){
		ig_intr_md_for_tm.ucast_egress_port = port;
		ig_intr_md_for_tm.qid = qid;
	}

	action l2_switch(PortId_t port){
		forward(port);
	}
	
	
	action l2_drop(){
		drop();
	}
	

	table l2_forward {
		key = {
			hdr.ethernet.dst_addr: exact;
		}
		actions = {
			l2_switch;
			route_init_courier_pkt;
			@defaultonly l2_drop;
		}
		size = 1024;
		const default_action = l2_drop();
	}

	/* action remove_pktgen_add_ether(){
        hdr.pktgen_timer.setInvalid();
        hdr.remaining_ethernet.setInvalid();

        hdr.ethernet.setValid();
        hdr.ethernet.dst_addr = SENDER_SW_ADDR; 
        hdr.ethernet.src_addr = RECEIVER_SW_ADDR; 
        hdr.ethernet.ether_type = ether_type_t.IPV4;
    } */

	action send_to_lpbk_port(){
		forward(ig_meta.port_md.lpbk_port);
		ig_intr_md_for_tm.bypass_egress = 1; // skip egress processing
	}

	action decap_linkradar_hdr(){
		// decap
		hdr.linkradar_data.setInvalid();
		hdr.ethernet.ether_type = ether_type_t.IPV4;
	}

	action mark_retx_pkt(){
		hdr.ethernet.src_addr[47:40] = 0xAA;
	}

	action decap_linkradar_data_and_rx_buffered_hdrs(){
		decap_linkradar_hdr();
		hdr.linkradar_rx_buffered.setInvalid();
	}

	action generate_ig_mirror_lack_update() {
		ig_intr_md_for_dprsr.mirror_type = IG_MIRROR_LACK_UPDATE;
		ig_meta.mirror_session = MIRROR_SESSION_LACK_UPDATE;

		ig_meta.internal_hdr_type = INTERNAL_HDR_TYPE_IG_MIRROR;
    	ig_meta.internal_hdr_info = (bit<4>)IG_MIRROR_LACK_UPDATE;

		ig_meta.ingress_port = ig_meta.port_md.orig_ig_port[7:0];
		ig_meta.leading_ack = hdr.linkradar_data.seq_no;
		ig_meta.leading_ack_era = hdr.linkradar_data.era;	
	}

	Register<seq_no_t,bit<8>>(MAX_PORTS,0) reg_expected_seq_no;
	RegisterAction<seq_no_t,bit<8>,seq_no_t>(reg_expected_seq_no) do_get_update_expected_seq_no_normal = {
		void apply(inout seq_no_t reg_val, out seq_no_t rv){
			rv = reg_val;
			reg_val = hdr.linkradar_data.seq_no + 1;
		}
	};
	action get_update_expected_seq_no_normal(){
		ig_meta.expected_seq_no = do_get_update_expected_seq_no_normal.execute(ig_meta.port_md.orig_ig_port[7:0]);
	}
	RegisterAction<seq_no_t,bit<8>,seq_no_t>(reg_expected_seq_no) read_expected_seq_no = {
		void apply(inout seq_no_t reg_val, out seq_no_t rv){
			rv = reg_val;
		}
	};
	action get_curr_expected_seq_no(){
		ig_meta.curr_expected_seq_no = read_expected_seq_no.execute(ig_meta.hard_coded_36);
		// ig_meta.curr_expected_seq_no = reg_expected_seq_no.read(ig_meta.port_md.orig_ig_port[7:0]);
	}

	RegisterAction<seq_no_t,bit<8>,seq_no_t>(reg_expected_seq_no) do_get_update_expected_seq_no_dummy = {
		void apply(inout seq_no_t reg_val, out seq_no_t rv){
			rv = reg_val;
			reg_val = hdr.linkradar_data.seq_no;
		}
	};
	action get_update_expected_seq_no_dummy(){
		ig_meta.expected_seq_no = do_get_update_expected_seq_no_dummy.execute(ig_meta.port_md.orig_ig_port[7:0]);
	}

	table get_update_expected_seq_no {
		key = {
			hdr.linkradar_data.dummy: exact;
		}
		actions = {
			get_update_expected_seq_no_normal;
			get_update_expected_seq_no_dummy;
		}
		size = 2;

		const entries = {
			0: get_update_expected_seq_no_normal();
			1: get_update_expected_seq_no_dummy();
		}
	}

	action calc_pkts_lost(){
		ig_meta.pkts_lost = hdr.linkradar_data.seq_no - ig_meta.expected_seq_no;
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

	action add_bridged_metadata(){
		hdr.bridged_meta.setValid();
        hdr.bridged_meta.type = INTERNAL_HDR_TYPE_BRIDGED_META;
        hdr.bridged_meta.info = 0;
	}

	// action mark_to_report_affected_flow(){
	// 	hdr.bridged_meta.affected_flow = 1;
	// }

	DirectCounter<bit<64>>(CounterType_t.PACKETS_AND_BYTES) loss_notify_cntr;

	action do_generate_loss_notification(MirrorId_t mirror_session){
		// instruct mirroring to the deparser
		ig_intr_md_for_dprsr.mirror_type = IG_MIRROR_LOSS_NOTIFICATION;
		ig_meta.mirror_session = mirror_session;

		// set internal_hdr for eg_parser
		ig_meta.internal_hdr_type = INTERNAL_HDR_TYPE_IG_MIRROR;
    	ig_meta.internal_hdr_info = (bit<4>)IG_MIRROR_LOSS_NOTIFICATION;

		// set data to put inside the ig_mirror hdr
		// as metadata: 
		// hole_size <-- already present as ig_meta.pkts_lost
		// first_lost_seq_no <-- already present as ig_meta.expected_seq_no

		// *** The following are now done by set_loss_notification_meta_normal():
		// ig_meta.leading_ack = hdr.linkradar_data.seq_no;
		// ig_meta.leading_ack_era = hdr.linkradar_data.era;

		loss_notify_cntr.count();
	}


	table generate_loss_notification{
		actions = {
			do_generate_loss_notification;
			@defaultonly nop;
		}
		key = {
			ig_meta.port_md.orig_ig_port: exact;
		}
		size = MAX_PROTECTED_PORTS;
		default_action = nop;
		counters = loss_notify_cntr;
	}

	Register<bit<32>,bit<1>>(1,0) reg_pkt_record_idx;
	RegisterAction<bit<32>,bit<1>,bit<32>>(reg_pkt_record_idx) read_update_pkt_record_idx = {
		void apply(inout bit<32> reg_val, out bit<32> rv){
			rv = reg_val;

			if(reg_val < MAX_PKT_RECORDS){
				reg_val = reg_val + 1;
			}
		}
	};
	action get_next_pkt_record_idx(){
		ig_meta.pkt_record_idx = read_update_pkt_record_idx.execute(0);
	}

	Register<pkt_record_t, bit<32>>(MAX_PKT_RECORDS) reg_pkt_records;
	RegisterAction<pkt_record_t, bit<32>, bit<32>>(reg_pkt_records) write_pkt_record = {
		void apply(inout pkt_record_t reg_val, out bit<32> rv){
			reg_val.seq_no = ig_meta.pkt_record.seq_no;
			reg_val.ts = ig_meta.pkt_record.ts;
		}
	};

	action insert_pkt_record(){
		write_pkt_record.execute(ig_meta.pkt_record_idx);
	}

	action prepare_pkt_record(){
		ig_meta.pkt_record.seq_no = hdr.linkradar_data.seq_no;
		ig_meta.pkt_record.ts = ig_intr_md_from_prsr.global_tstamp[15:0]; 
	}

	action set_loss_notification_lack_normal(){
		ig_meta.leading_ack = hdr.linkradar_data.seq_no;
		// ig_meta.leading_ack_era = hdr.linkradar_data.era;
	}

	action set_loss_notification_lack_dummy(){
		ig_meta.leading_ack = hdr.linkradar_data.seq_no - 1;
		// ig_meta.leading_ack_era = hdr.linkradar_data.era;
	}

	action set_loss_notification_lack_era(){
		ig_meta.leading_ack_era = hdr.linkradar_data.era;
	}

	action flip_loss_notification_lack_era(){
		ig_meta.leading_ack_era = ~ig_meta.leading_ack_era;
	}

	Register<ack_record_t,bit<8>>(MAX_PORTS, {0,TIMEOUT_VAL_100NS}) reg_ack;
	RegisterAction<ack_record_t,bit<8>,bit<16>>(reg_ack) get_check_increment_ack = {
		void apply(inout ack_record_t reg_val, out bit<16> rv){		
			rv = reg_val.ack_no;
			if(reg_val.ack_no == hdr.linkradar_data.seq_no){
				reg_val.ack_no = reg_val.ack_no + 1;
				reg_val.time_remaining = TIMEOUT_VAL_100NS; // ig_meta.timeout_val_100ns; //1; // ig_intr_md_from_prsr.global_tstamp[15:0];
			}
		}
	};

	RegisterAction<ack_record_t,bit<8>,bit<1>>(reg_ack) check_timeout_increment_ack = {
		void apply(inout ack_record_t reg_val, out bit<1> rv){		
			// rv = reg_val.ack_no;
			// ack_record_t orig_val = reg_val;
			bit<16> tmp = reg_val.ack_no - ig_meta.curr_expected_seq_no;

			bool expected_ack_nos_diff = (tmp != 0);
			bool timedout = (reg_val.time_remaining == 0);

			rv = 0;
			
			if(expected_ack_nos_diff){
				if(timedout){
					reg_val.ack_no = reg_val.ack_no + 1;
					reg_val.time_remaining = TIMEOUT_VAL_100NS; // ig_meta.timeout_val; // 16w1;
					rv = 1;
				}
				else{ // not timedout, then decrement time and wait.
					reg_val.time_remaining =  reg_val.time_remaining - 1; // 16w0;
				}
			}
			// else{
			// 	reg_val.ack_no = reg_val.ack_no;
			// 	reg_val.changed = 16w0;
			// }
		
		}
	};

	action get_check_update_curr_ack(){
		ig_meta.curr_ack = get_check_increment_ack.execute(ig_meta.blocking_mode_orig_ig_port); 
	}

	action check_timeout_update_curr_ack(){
		ig_meta.ack_timeout_triggered = check_timeout_increment_ack.execute(ig_meta.hard_coded_36); 
	}


	Register<bit<8>,bit<8>>(MAX_PORTS,0) reg_ack_era;

	RegisterAction<bit<8>,bit<8>,bit<8>>(reg_ack_era) do_get_update_ack_era = {
		void apply(inout bit<8> reg_val, out bit<8> rv){
			rv = reg_val;		
			reg_val = ~reg_val; // toggle 0 and 1
		}
	};

	RegisterAction<bit<8>,bit<8>,bit<8>>(reg_ack_era) do_get_ack_era = {
		void apply(inout bit<8> reg_val, out bit<8> rv){
			rv = reg_val;
		}
	};

	action get_update_ack_era(){
		ig_meta.curr_ack_era = (bit<1>)do_get_update_ack_era.execute(ig_meta.blocking_mode_orig_ig_port);
	}

	action get_ack_era(){
		ig_meta.curr_ack_era = (bit<1>)do_get_ack_era.execute(ig_meta.blocking_mode_orig_ig_port);
	}

	action get_orig_ig_port_from_rx_buffered_hdr(){
		ig_meta.blocking_mode_orig_ig_port = hdr.linkradar_rx_buffered.orig_ig_port;
	}

	action get_orig_ig_port_from_port_md(){
		ig_meta.blocking_mode_orig_ig_port = ig_meta.port_md.orig_ig_port[7:0];
	}

	DirectCounter<bit<64>>(CounterType_t.PACKETS) era_correction_cntr;

	action adjust_seq_nos(){
		ig_meta.pkt_seq_no = ig_meta.pkt_seq_no - SEQ_NUMBERS_HALF_RANGE;
		ig_meta.curr_ack = ig_meta.curr_ack - SEQ_NUMBERS_HALF_RANGE;
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
			ig_meta.curr_ack_era: exact;
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

	action get_min_curr_ack_seq_no(){
		ig_meta.min_val = min(ig_meta.curr_ack, ig_meta.pkt_seq_no);
	}

	action add_rx_buffered_hdr_and_recirculate(){
		hdr.linkradar_data.rx_buffered = 1;
		hdr.linkradar_rx_buffered.setValid();
		hdr.linkradar_rx_buffered.orig_ig_port = ig_meta.blocking_mode_orig_ig_port;
		ig_intr_md_for_tm.ucast_egress_port = RECIRC_PORT_PIPE_0;
		ig_intr_md_for_tm.qid = RECIRC_PORT_RX_BUFFER_QID;
		
		// NOTE: let's not bypass egress for now. Buys more time for reTx to arrive.
		// ig_intr_md_for_tm.bypass_egress = 1;
	}


	//  #########  RANDOM PKT DROPPING  #########
	Random<random_gen_bitwidth_t>() random; 

	action get_curr_random_number(){
		ig_meta.curr_rand_number = random.get();
	}

	action do_emulate_pkt_drop(){
		// Redirect the pkt to affected_flows monitoring
		ig_intr_md_for_tm.ucast_egress_port = AFFECTED_FLOWS_DEV_PORT;
		ig_intr_md_for_tm.bypass_egress = 1; // skip egress processing
		decap_linkradar_hdr(); // decap linkradar hdr
		// exit; // skip rest of the pipeline processing
	}

	action nop_emulate_pkt_drop(){}

	table emulate_random_pkt_drop {
		key = {
			ig_meta.curr_rand_number: exact;
		}
		actions = {
			do_emulate_pkt_drop;
			// nop_emulate_pkt_drop;
			send_to_lpbk_port;
		}
		const default_action = send_to_lpbk_port(); // nop_emulate_pkt_drop();
		size = RANDOM_DROP_TABLE_SIZE;
	}

	//  #########  RANDOM PKT DROPPING (END) #########

	Register<bit<32>,bit<16>>(10, 0) reg_hole_sizes;
	RegisterAction<bit<32>,bit<16>,bit<32>>(reg_hole_sizes) incr_hole_size_count = {
		void apply(inout bit<32> reg_val, out bit<32> rv){
			reg_val = reg_val + 1; 
		}
	};
	action record_hole_size_count(){
		incr_hole_size_count.execute(ig_meta.pkts_lost);
	}

	action remove_pktgen_add_ether(){
		hdr.pktgen_timer.setInvalid();
        hdr.remaining_ethernet.setInvalid();
		hdr.ethernet.setValid();
	}

	action add_pfc_hdr(){
		hdr.ethernet.ether_type = ether_type_t.PAUSE_PFC;
		hdr.ethernet.dst_addr = PAUSE_PFC_ETHER_DST_ADDR;
		hdr.ethernet.src_addr = PAUSE_PFC_ETHER_SRC_ADDR;

		// hdr.ether_pfc should already be valid for a pktgen pkt
		// since we are parsing the padded 0's as hdr.ether_pfc
		hdr.ether_pfc.setValid(); // yet add again. Make code portable!
		hdr.ether_pfc.op_code = PFC_OP_CODE;
		hdr.ether_pfc.c1_enabled = 1;
	}

	action do_add_pfc_hdr_and_route(PortId_t egress_port){
		add_pfc_hdr(); // sets c1_enabled

		ig_intr_md_for_tm.ucast_egress_port = egress_port;
		ig_intr_md_for_tm.qid = LOSS_NOTIFICATION_QID;
		// OLD: for PFC on each timeout
		// ig_intr_md_for_tm.bypass_egress = 1;
		// hdr.ether_pfc.c1_quanta = c1_quanta;
	}

	table add_pfc_hdr_and_route{
		actions = {
			@defaultonly do_add_pfc_hdr_and_route;
			@defaultonly drop;
		}
		key = {
			// TODO: for multiple ports, this could be pktgen pkt/batch id
			// eg_intr_md.egress_port: exact;
		}
		size = 1;
		default_action = drop();
	}

	#if MEASURE_RETX_LATENCY
	// ------------ RETX LATENCY MEASUREMENT ---------------
	Register<bit<32>,bit<16>>(MAX_SEQ_NUMBERS, 0) reg_lost_timestamps;

	RegisterAction<bit<32>,bit<16>,bit<32>>(reg_lost_timestamps) read_reset_lost_timestamp = {
		void apply(inout bit<32> reg_val, out bit<32> rv){
			rv = reg_val;
			reg_val = 0; 
		}
	};
	
	action record_lost_timestamp(){
		reg_lost_timestamps.write(ig_meta.expected_seq_no, ig_intr_md_from_prsr.global_tstamp[31:0]);
	}

	action lookup_reset_lost_timestamp(){
		ig_meta.lost_timestamp = read_reset_lost_timestamp.execute(hdr.linkradar_data.seq_no);
	}

	action add_timestamps_and_reroute(){
		hdr.ipv4.src_addr = ig_meta.lost_timestamp; 
		hdr.ipv4.dst_addr = ig_intr_md_from_prsr.global_tstamp[31:0];
		ig_intr_md_for_tm.ucast_egress_port = RETX_LATENCY_SERVER_EG_PORT;
	}
	#endif
	// -----------------------------------------------------

	// ------------ CONFIGURABLE TIMEOUT VALUE ---------------
	// TODO: fix the compiler error for reg_ack
	/* Register<bit<16>,bit<8>>(256, 0) reg_timeout_val;

	action get_timeout_val(){
		ig_meta.timeout_val = reg_timeout_val.read(36);
	} */
	// -------------------------------------------------------

	// -------------------  MEASURING PFC DELAYS  -----------------------------
	#if MEASURE_PFC_DELAYS
	Register<bit<32>,bit<1>>(1, 0) reg_prev_ts;
	RegisterAction<bit<32>,bit<1>,bit<32>>(reg_prev_ts) read_write_prev_ts = {
		void apply(inout bit<32> reg_val, out bit<32> rv){
			rv = reg_val;
			reg_val = ig_intr_md_from_prsr.global_tstamp[31:0];
		}
	};

	action get_set_prev_pkt_time(){
		ig_meta.prev_ts = read_write_prev_ts.execute(0);
	}

	Register<bit<32>,bit<1>>(1,0) reg_pkt_ipg_record_idx;
	RegisterAction<bit<32>,bit<1>,bit<32>>(reg_pkt_ipg_record_idx) read_update_pkt_ipg_record_idx = {
		void apply(inout bit<32> reg_val, out bit<32> rv){
			rv = reg_val;

			if(reg_val < MAX_PKT_IPG_RECORDS){
				reg_val = reg_val + 1;
			}
		}
	};
	action get_next_pkt_ipg_record_idx(){
		ig_meta.pkt_ipg_record_idx = read_update_pkt_ipg_record_idx.execute(0);
	}


	Register<pkt_ipg_record_t, bit<32>>(MAX_PKT_IPG_RECORDS) reg_pkt_ipg_records;
	RegisterAction<pkt_ipg_record_t, bit<32>, bit<32>>(reg_pkt_ipg_records) write_pkt_ipg_record = {
		void apply(inout pkt_ipg_record_t reg_val, out bit<32> rv){
			reg_val.prev_ts = ig_meta.prev_ts;
			reg_val.curr_ts = ig_intr_md_from_prsr.global_tstamp[31:0];
		}
	};

	action insert_pkt_ipg_record(){
		write_pkt_ipg_record.execute(ig_meta.pkt_ipg_record_idx);
	}

	/* action prepare_pkt_record(){
		ig_meta.pkt_record.seq_no = hdr.linkradar_data.seq_no;
		ig_meta.pkt_record.ts = ig_intr_md_from_prsr.global_tstamp[15:0]; 
	} */

	action compute_time_diff(){
		ig_meta.time_diff = ig_intr_md_from_prsr.global_tstamp[31:0] - ig_meta.prev_ts;
	}

	action get_min(){
		ig_meta.min_val_ipg = min(ig_meta.time_diff, MAX_POSSIBLE_IPG_NS);
	}
	#endif  // end of #if MEASURE_PFC_DELAYS
	// --------------------------------------------------------------------------

	apply {
		
		if(hdr.pktgen_timer.isValid()){ // Pktgen pkt received on dev_port 68. 
			// Forward it out on wire.
			// remove_pktgen_add_ether(); // <--- OLD
			ig_meta.hard_coded_36 = 36;

			// get_timeout_val(); // TODO: fix this later

			get_curr_expected_seq_no(); // reads into ig_meta.expected_seq_no
			// sets ig_meta.ack_timeout_triggered on timeout update of ack
			check_timeout_update_curr_ack(); 
			if(ig_meta.ack_timeout_triggered == 1){ // ack was timeout updated
				ig_debug_counter.count(2);
				// ----- Send PFC PAUSE Frame -----
				// remove_pktgen_add_ether();
				// add_pfc_hdr_and_route.apply(); // either drops or sends PFC
				// --------------------------------
			}
			else{
				ig_debug_counter.count(1);
				// drop();
			}
			// every timeout pkt transformed into PFC pkt. 
			// Then sent to egress pipe.
			remove_pktgen_add_ether();
			add_pfc_hdr_and_route.apply();
		}
		else if(ig_meta.port_md.filter_via_lpbk == 1){ // pkts need to be filtered via lpbk
			get_curr_random_number();
			emulate_random_pkt_drop.apply(); // default action: send_to_lpbk_port()
		}
		else{ // ALL: protected (+reTx) pkts, RX buffered (blocking mode), unprotected pkts
			l2_forward.apply();

			
			if(ig_meta.port_md.protect == 1 && hdr.linkradar_data.isValid()){
				// ingress port AND traffic are protected
				
				// Step 1: check whether normal pkt or reTx packet
				if(hdr.linkradar_data.reTx == 0){ // normal pkt or dummy pkt
					
					// prepare_meta_for_loss_notification.apply();
					// prepare_lack_era_for_loss_notification.apply();
					set_loss_notification_lack_era(); // used or not depends on ig_meta.pkts_lost

					// **** HOLE DETECTION 
					get_update_expected_seq_no.apply(); // get_update_expected_seq_no();
					calc_pkts_lost(); // fills ig_meta.pkts_lost
					if(ig_meta.pkts_lost != 0){ // some packets were lost
					
						generate_loss_notification.apply();

						if(hdr.linkradar_data.dummy == 0){ // only for normal pkt
							// mark_to_report_affected_flow();
							set_loss_notification_lack_normal();
						}
						else if(hdr.linkradar_data.dummy == 1){ // dummy pkt
							
							set_loss_notification_lack_dummy();
							
							if(hdr.linkradar_data.seq_no == 0){ // adjust the era
								flip_loss_notification_lack_era();
							}
							
							drop(); // loss notification would still be generated
						}

						debug_count();
						#if DEBUG
						record_hole_size_count();
						#endif

						#if MEASURE_RETX_LATENCY
						record_lost_timestamp();
						#endif
					}
					else{ // no holes detected with current packet
						// do a normal lack update only for normal pkts
						if(hdr.linkradar_data.dummy == 0){
							generate_ig_mirror_lack_update();
							ig_debug_counter2.count(0);
						}
						else if(hdr.linkradar_data.dummy == 1){
							drop(); // dummy pkt duplicate. Drop it!
						}
					}

					
				} // end of if hdr.linkradar_data.reTx == 0
				else if (hdr.linkradar_data.reTx == 1){ // just let the pkt go
					// TODO: complete the de-dup logic
					if (hdr.ethernet.dst_addr[47:32] == RECEIVER_SW_ADDR_HI_16){
						mark_retx_pkt();
					}
					#if MEASURE_RETX_LATENCY
					lookup_reset_lost_timestamp(); // sets ig_meta.lost_timestamp
					if(ig_meta.lost_timestamp != 0){
						// this does de-duplication in a way
						// sends timestamps as per the 1st reTx copy
						add_timestamps_and_reroute();
					}
					#endif
				} // end of hdr.linkradar_data.reTx == 1

				// **********  MEASURING PFC DELAYS  **************
				#if MEASURE_PFC_DELAYS
				get_set_prev_pkt_time(); // fills ig_meta.prev_ts
				// prepare_pkt_ipg_record();
				compute_time_diff(); // fills ig_meta.time_diff
				get_min(); // ig_meta.min_val_ipg = min(ig_meta.time_diff, MAX_POSSIBLE_IPG_NS);
				if(ig_meta.min_val_ipg == MAX_POSSIBLE_IPG_NS){ 
					// ig_meta.time_diff > MAX_POSSIBLE_IPG_NS
					get_next_pkt_ipg_record_idx();
					insert_pkt_ipg_record();
				}
				#endif
				// **************************************

				// **********  DEBUGGING/EVALUATION  **************
				#if DEBUG
				// prepare_pkt_record();
				// get_next_pkt_record_idx();
				// insert_pkt_record();
				#endif
				// **************************************
			
			} // end of if(ig_meta.port_md.protect == 1 && hdr.linkradar_data.isValid())


			if(hdr.linkradar_data.isValid() && hdr.linkradar_data.dummy == 0){ // protected normal/reTx pkts, RX buffered pkts

				// fill ig_meta.blocking_mode_orig_ig_port depending on the pkt type
				if(hdr.linkradar_data.rx_buffered == 0){ // normal protected or reTx
					get_orig_ig_port_from_port_md();
				}
				else{ // rx_buffered pkt
					get_orig_ig_port_from_rx_buffered_hdr();
				}

				if(hdr.linkradar_data.blocking_mode == 0){ 
					// protected normal/reTx pkts
					decap_linkradar_hdr(); // decap and let them go!
					ig_debug_counter.count(3);
				}
				else{ // 3 types: protected normal/reTx pkts, RX buffered pkts w/ blocking mode
					// ********** BLOCKING MODE **********
					// l2_forward above MUST work. 
					// Blocking mode overwrites ucast_egress_port and qid (as needed)
					ig_debug_counter.count(0);
					
					// get_timeout_val(); // TODO: fix this later

					// Step 1: get ig_meta.curr_ack
					get_check_update_curr_ack(); // also updates reg_val if matching seq_no
					
					if(ig_meta.curr_ack == hdr.linkradar_data.seq_no){ // means it got updated
						// decap and let go
						decap_linkradar_data_and_rx_buffered_hdrs();
						
						if(ig_meta.curr_ack == MAX_SEQ_NO){ // curr_ack is max && ack got updated
							// so update the curr_ack_era
							get_update_ack_era();
						}
					}
					else{ // need to do comparison
						get_ack_era();
						era_correction.apply();
						get_min_curr_ack_seq_no(); // fills ig_meta.min_val
						if (ig_meta.min_val == ig_meta.curr_ack){ // seq_no > curr_ack
							add_rx_buffered_hdr_and_recirculate();
						}
						else{ // seq_no < curr_ack
							drop(); // de-duplication logic for blocking mode 
						}
					}

				} // end of else block (blocking mode)
			} // end of if(hdr.linkradar_data.isValid() && hdr.linkradar_data.dummy == 0)
		
		} // end of the BIG else block: non-PktGen pkts + pkts not requiring filtering
		  // This includes: protected (+reTx) pkts, RX buffered (blocking mode), unprotected pkts
		

		// NOTE: We want to piggyback leading_ack on normal pkts. 
		// CANNOT bypass the egress processing for them!

		if(ig_intr_md_for_tm.bypass_egress == 0){
			add_bridged_metadata(); // every pkt going to egress should hv the INTERNAL_HEADER
		}

	} // end of ingress control apply block

}  // End of SwitchIngressControl

// @pa_no_overlay("egress","eg_meta.pfc_gen_req")
control SwitchEgress(
    inout header_t hdr,
    inout eg_metadata_t eg_meta,
    in egress_intrinsic_metadata_t eg_intr_md,
    in egress_intrinsic_metadata_from_parser_t eg_intr_md_from_prsr,
    inout egress_intrinsic_metadata_for_deparser_t eg_intr_md_for_dprsr,
    inout egress_intrinsic_metadata_for_output_port_t eg_intr_md_for_oport){
	
	Counter<bit<64>,debug_counter_idx_t>(DEBUG_COUNTER_SIZE,CounterType_t.PACKETS_AND_BYTES) eg_debug_counter;

	action drop(){
		eg_intr_md_for_dprsr.drop_ctl = 0x1;
	}

	action nop(){}

	Register<seq_no_t,bit<8>>(MAX_PORTS,0) reg_leading_ack;
	RegisterAction<seq_no_t,bit<8>,seq_no_t>(reg_leading_ack) write_reg_leading_ack = {
		void apply(inout seq_no_t reg_val, out seq_no_t rv){
			reg_val = eg_meta.ig_mirror_lack_update.leading_ack;
		}
	};
	RegisterAction<seq_no_t,bit<8>,seq_no_t>(reg_leading_ack) read_reg_leading_ack = {
		void apply(inout seq_no_t reg_val, out seq_no_t rv){
			rv = reg_val;
		}
	};
	action record_leading_ack(){ // set by lack_update ig_mirrored pkts
		// reg_leading_ack.write(eg_meta.ig_mirror_lack_update.ingress_port, eg_meta.ig_mirror_lack_update.leading_ack);
		write_reg_leading_ack.execute(eg_meta.ig_mirror_lack_update.ingress_port);
	}
	action retrieve_leading_ack(){ // read by courier/normal pkts
		// hdr.linkradar_lack.leading_ack = reg_leading_ack.read(eg_intr_md.egress_port[7:0]);
		hdr.linkradar_lack.leading_ack = read_reg_leading_ack.execute(eg_intr_md.egress_port[7:0]); 
	}

	Register<bit<8>,bit<8>>(MAX_PORTS,0) reg_leading_ack_era;
	RegisterAction<bit<8>,bit<8>,bit<8>>(reg_leading_ack_era) write_reg_leading_ack_era = {
		void apply(inout bit<8> reg_val, out bit<8> rv){
			reg_val = (bit<8>)eg_meta.ig_mirror_lack_update.leading_ack_era;
		}
	};
	RegisterAction<bit<8>,bit<8>,bit<8>>(reg_leading_ack_era) read_reg_leading_ack_era = {
		void apply(inout bit<8> reg_val, out bit<8> rv){
			rv = reg_val;
		}
	};
	action record_leading_ack_era(){
		// reg_leading_ack_era.write(eg_meta.ig_mirror_lack_update.ingress_port, (bit<8>)eg_meta.ig_mirror_lack_update.leading_ack_era);
		write_reg_leading_ack_era.execute(eg_meta.ig_mirror_lack_update.ingress_port); 
	}
	action retrieve_leading_ack_era(){ // read by courier/normal pkts
		// hdr.linkradar_lack.era = (bit<1>)reg_leading_ack_era.read(eg_intr_md.egress_port[7:0]);
		hdr.linkradar_lack.era = (bit<1>)read_reg_leading_ack_era.execute(eg_intr_md.egress_port[7:0]);
	}

	Register<bit<8>,bit<8>>(MAX_PORTS,0) reg_leading_ack_notify_count;
	RegisterAction<bit<8>,bit<8>,bit<1>>(reg_leading_ack_notify_count) do_check_if_lack_pending = {
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
	action check_if_lack_pending(){
		eg_meta.is_lack_pending = do_check_if_lack_pending.execute(eg_intr_md.egress_port[7:0]);
		// eg_intr_md_for_dprsr.drop_ctl = read_decrement_leading_ack_notify_count.execute(eg_intr_md.egress_port[7:0]);
	}
	action set_leading_ack_notify_max_count(){
		reg_leading_ack_notify_count.write(eg_meta.ig_mirror_lack_update.ingress_port, eg_meta.leading_ack_notify_max_count);
	}
	action set_leading_ack_notify_max_count_to_zero(){
		reg_leading_ack_notify_count.write(eg_intr_md.egress_port[7:0], 0);
	}

	action do_get_leading_ack_notify_max_count(bit<8> count){
		eg_meta.leading_ack_notify_max_count = count; 
	}
	table get_leading_ack_notify_max_count{
		actions = {
			do_get_leading_ack_notify_max_count;
			nop;
		}
		key = {
			eg_meta.ig_mirror_lack_update.ingress_port: exact;
		}
		size = MAX_PROTECTED_PORTS;
		default_action = nop;
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

	action do_get_courier_pkt_mirror_session(MirrorId_t mirror_session){
		eg_meta.mirror_session = mirror_session;
	}
	table get_courier_pkt_mirror_session{
		actions = {
			do_get_courier_pkt_mirror_session;
			nop;
		}
		key = {
			eg_intr_md.egress_port: exact;
		}
		size = MAX_PROTECTED_PORTS;
		default_action = nop;
	}

	DirectCounter<bit<64>>(CounterType_t.PACKETS_AND_BYTES) courier_pkt_cntr;

	action mirror_courier_pkt(){
		// prepare the internal header for EG_MIRROR
		eg_meta.internal_hdr_type = INTERNAL_HDR_TYPE_EG_MIRROR;
    	eg_meta.internal_hdr_info = (bit<4>)EG_MIRROR_COURIER_PKT;

		// set for mirroring
		eg_intr_md_for_dprsr.mirror_type = EG_MIRROR_COURIER_PKT;
		// eg_meta.mirror_session <== already set by tbl get_courier_pkt_mirror_session
		courier_pkt_cntr.count();
	}

	action mirror_drop_courier_pkt(){
		mirror_courier_pkt();
		drop();
	}

	action add_linkradar_lack_hdr(){
		hdr.ethernet.ether_type = ether_type_t.LINKRADAR;
		hdr.linkradar_lack.setValid();
		hdr.linkradar_lack.type = LINKRADAR_HDR_TYPE_LACK;
		hdr.linkradar_lack.is_piggy_backed = 1;
		courier_pkt_cntr.count();
	}

	action nop_lack_update(){
		courier_pkt_cntr.count();
	}

	table add_lack_hdr_or_drop_mirror_courier_pkt{
		actions = {
			add_linkradar_lack_hdr;
			mirror_drop_courier_pkt;
			mirror_courier_pkt;
			nop_lack_update;
		}
		key = {
			eg_meta.is_lack_pending:   exact;
			hdr.linkradar_lack.isValid(): exact;
		}
		size = 4;
		default_action = nop_lack_update;

		const entries = {
			(0, false): nop_lack_update(); // do nothing to the normal pkt
			(1, false): add_linkradar_lack_hdr(); // piggyback on normal pkt
			(0, true): mirror_drop_courier_pkt(); // mirror and drop courier packet
			(1, true): mirror_courier_pkt(); // let the courier pkt go, but mirror it!
		}

		counters = courier_pkt_cntr;
	}

	action add_lack_loss_notification_hdrs(){ // lack + loss notification
		hdr.ethernet.ether_type = ether_type_t.LINKRADAR;
		hdr.ethernet.dst_addr = SENDER_SW_ADDR;
		hdr.ethernet.src_addr = RECEIVER_SW_ADDR;

		hdr.linkradar_lack.setValid();
		hdr.linkradar_loss_notification.setValid();
		
		hdr.linkradar_lack.type = LINKRADAR_HDR_TYPE_LACK_LOSS_NOTIFY;
		hdr.linkradar_lack.is_piggy_backed = 0; // to be dropped at the sender
	}
	
	action copy_data_to_loss_notification_hdrs(){
		// copy lack and lack_era
		hdr.linkradar_lack.leading_ack = eg_meta.ig_mirror_loss_notification.leading_ack;
		hdr.linkradar_lack.era = eg_meta.ig_mirror_loss_notification.leading_ack_era;

		// copy first_lost and hole size
		hdr.linkradar_loss_notification.first_lost_seq_no = eg_meta.ig_mirror_loss_notification.first_lost_seq_no;
		hdr.linkradar_loss_notification.hole_size = (bit<8>)eg_meta.ig_mirror_loss_notification.hole_size;
	}

	action do_add_pause_quanta(bit<16> pause_quanta){
		hdr.ether_pause.pause_quanta = pause_quanta;
	}

	table add_pause_quanta{
		actions = {
			do_add_pause_quanta;
			nop;
		}
		key = {
			eg_intr_md.egress_port: exact;
		}
		size = 256;
		default_action = nop();
	}

	action do_add_pfc_c1_quanta(bit<16> c1_quanta){
		hdr.ether_pfc.c1_quanta = c1_quanta;
	}

	table add_pfc_c1_quanta{
		actions = {
			do_add_pfc_c1_quanta;
			nop;
		}
		key = {
			eg_intr_md.egress_port: exact;
		}
		size = 256;
		default_action = nop();
	}

	action add_ethernet_pause_hdr(){
		hdr.ethernet.ether_type = ether_type_t.PAUSE_PFC;
		hdr.ethernet.dst_addr = PAUSE_PFC_ETHER_DST_ADDR;
		hdr.ethernet.src_addr = PAUSE_PFC_ETHER_SRC_ADDR;

		hdr.ether_pause.setValid();
		hdr.ether_pause.op_code = PAUSE_OP_CODE;
	}

	action add_ethernet_pfc_hdr(){
		hdr.ethernet.ether_type = ether_type_t.PAUSE_PFC;
		hdr.ethernet.dst_addr = PAUSE_PFC_ETHER_DST_ADDR;
		hdr.ethernet.src_addr = PAUSE_PFC_ETHER_SRC_ADDR;

		hdr.ether_pfc.setValid(); 
		hdr.ether_pfc.op_code = PFC_OP_CODE;
		hdr.ether_pfc.c1_enabled = 1;
	}

	
	// action mirror_to_report_affected_flow(){
	// 	// setup mirroring
	// 	eg_intr_md_for_dprsr.mirror_type = EG_MIRROR_AFFECTED_FLOW;
	// 	eg_meta.mirror_session = MIRROR_SESSION_AFFECTED_FLOWS;
	// 	// setup the internal hdr
	// 	eg_meta.internal_hdr_type = INTERNAL_HDR_TYPE_EG_MIRROR;
    // 	eg_meta.internal_hdr_info = (bit<4>)EG_MIRROR_AFFECTED_FLOW;
		
	// 	// (any) data to add to the mirroring internal hdr
	// 	// ig_meta.hole_size_to_report = ig_meta.pkts_lost;
	// 	// ig_meta.ipg_to_report = ig_meta.bridged.ig_mac_ts - ig_meta.prev_mac_ts;
	// }

	// ##### ECN Marking #####
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
		eg_meta.exceeded_ecn_marking_threshold = cmp_ecn_marking_threshold.execute(0);
	}

	action mark_ecn_ce_codepoint(){
		hdr.ipv4.ecn = 0b11;
	}
	// ##### ECN Marking (end) #####

	// ##### Queue threshold based PFC (start) #####
	Register<bit<32>,bit<1>>(1,524287) reg_recirc_buffer_pfc_pause_threshold; // default = 2^19 - 1 
	RegisterAction<bit<32>,bit<1>,bit<1>>(reg_recirc_buffer_pfc_pause_threshold) cmp_recirc_buffer_pfc_pause_threshold = {
		void apply(inout bit<32> reg_val, out bit<1> rv){
			if((bit<32>)eg_intr_md.deq_qdepth >= reg_val){
				rv = 1;
			}
			else{
				rv = 0;
			}
		}
	};

	action check_recirc_buffer_pfc_pause_threshold(){
		eg_meta.exceeded_recirc_buffer_pfc_pause_threshold = cmp_recirc_buffer_pfc_pause_threshold.execute(0);
	}

	Register<bit<32>,bit<1>>(1,0) reg_recirc_buffer_pfc_resume_threshold;
	RegisterAction<bit<32>,bit<1>,bit<1>>(reg_recirc_buffer_pfc_resume_threshold) cmp_recirc_buffer_pfc_resume_threshold = {
		void apply(inout bit<32> reg_val, out bit<1> rv){
			if((bit<32>)eg_intr_md.deq_qdepth <= reg_val){
				rv = 1;
			}
			else{
				rv = 0;
			}
		}
	};

	action check_recirc_buffer_pfc_resume_threshold(){
		eg_meta.subceeded_recirc_buffer_pfc_resume_threshold = cmp_recirc_buffer_pfc_resume_threshold.execute(0);
	}

	Register<bit<8>, bit<8>>(MAX_PORTS, pfc_state_t.RESUMED) reg_pfc_curr_state;
	
	RegisterAction<bit<8>, bit<1>, bit<1>>(reg_pfc_curr_state) cmp_update_pfc_pause_state = {
		void apply(inout bit<8> reg_val, out bit<1> rv){
			if(reg_val == pfc_state_t.PAUSED){ // if already paused 
				// do nothing for reg_val (the state)
				rv = 0; // no need to send another pause frame
			}
			else{ // it is not already paused
				reg_val = pfc_state_t.PAUSED; // set the state to PAUSED
				rv = 1; // signal to send a PFC pause frame
			}
		}
	};
	action check_update_pfc_pause_state(){
		eg_meta.should_send_pfc_pause = cmp_update_pfc_pause_state.execute(0);
	}

	RegisterAction<bit<8>, bit<1>, bit<1>>(reg_pfc_curr_state) cmp_update_pfc_resume_state = {
		void apply(inout bit<8> reg_val, out bit<1> rv){
			if(reg_val == pfc_state_t.RESUMED){ // if already resumed
				// do nothing for reg_val (the state)
				rv = 0; // no need to send another resume frame
			}
			else{ // it is not already resumed
				reg_val = pfc_state_t.RESUMED; // set the state to RESUMED
				rv = 1; // signal to send a PFC resume frame
			}
		}
	};
	action check_update_pfc_resume_state(){
		eg_meta.should_send_pfc_resume = cmp_update_pfc_resume_state.execute(0);
	}

	action mirror_to_generate_pfc_frame(bit<16> quanta){
		// prepare the internal header for EG_MIRROR
		eg_meta.internal_hdr_type = INTERNAL_HDR_TYPE_EG_MIRROR;
    	eg_meta.internal_hdr_info = (bit<4>)EG_MIRROR_PFC_PKT;

		// set for mirroring
		eg_intr_md_for_dprsr.mirror_type = EG_MIRROR_PFC_PKT;
		eg_meta.mirror_session = MIRROR_SESSION_EG_PFC;

		eg_meta.pfc_quanta = quanta; 
	}

	// @stage(2)
	Register<bit<8>, bit<1>>(MAX_PORTS, PFC_GEN_REQ_DROP) reg_pfc_gen_req;

	RegisterAction<bit<8>, bit<1>, bit<8>>(reg_pfc_gen_req) set_pfc_gen_req_pause = {
		void apply(inout bit<8> reg_val, out bit<8> rv){
			reg_val = PFC_GEN_REQ_PAUSE;
		}
	};

	RegisterAction<bit<8>, bit<1>, bit<8>>(reg_pfc_gen_req) set_pfc_gen_req_resume = {
		void apply(inout bit<8> reg_val, out bit<8> rv){
			reg_val = PFC_GEN_REQ_RESUME;
		}
	};

	action schedule_to_generate_pfc_pause(){
		set_pfc_gen_req_pause.execute(0);
	}

	action schedule_to_generate_pfc_resume(){
		set_pfc_gen_req_resume.execute(0);
	}

	RegisterAction<bit<8>, bit<1>, bit<8>>(reg_pfc_gen_req) read_reset_pfc_gen_req = {
		void apply(inout bit<8> reg_val, out bit<8> rv){
			rv = reg_val;
			reg_val = PFC_GEN_REQ_DROP;
		}
	};

	action do_check_reset_pfc_gen_req(){
		eg_meta.pfc_gen_req = read_reset_pfc_gen_req.execute(0);
	}

	// NOTE: had to wrap into a table and fix stage #. 
	// Compiler issue otherwise: 2 copies of the reg_pfc_gen_req register
	@stage(4)
	table check_reset_pfc_gen_req{
		actions = {
			do_check_reset_pfc_gen_req;
		}
		key = {
			
		}
		size = 1;
		const default_action = do_check_reset_pfc_gen_req();
	}

	action drop_pfc_gen_pkt(){
		drop();
		eg_debug_counter.count(3);
	}

	action transform_pfc_gen_to_pause(){
		hdr.ether_pfc.c1_enabled = 1;
		hdr.ether_pfc.c1_quanta = MAX_PFC_QUANTA;
		eg_debug_counter.count(4);
	}

	action transform_pfc_gen_to_resume(){
		hdr.ether_pfc.c1_enabled = 1;
		hdr.ether_pfc.c1_quanta = 0;
		eg_debug_counter.count(5);
	}

	table gen_pfc_or_drop{
		actions = {
			transform_pfc_gen_to_pause;
			transform_pfc_gen_to_resume;
			drop_pfc_gen_pkt;
			@defaultonly nop;
		}
		key = {
			eg_meta.pfc_gen_req: exact;
		}
		size = 4;
		const default_action = nop();
		const entries = {
			PFC_GEN_REQ_DROP: drop_pfc_gen_pkt();
			PFC_GEN_REQ_PAUSE: transform_pfc_gen_to_pause();
			PFC_GEN_REQ_RESUME: transform_pfc_gen_to_resume();
		}
	}

	action copy_pfc_c1_quanta(){
		hdr.ether_pfc.c1_quanta = eg_meta.eg_mirror_pfc_pkt.pfc_quanta;
	}
	// ##### Queue threshold based PFC (end) #####


	// ##### PFC DELAY MEASUREMENT (start) #####
	#if MEASURE_PFC_DELAYS
	Register<bit<8>,bit<1>>(1, PFC_GEN_REQ_PAUSE) reg_pfc_toggle;

	RegisterAction<bit<8>,bit<1>,bit<8>>(reg_pfc_toggle) toggle_read_pfc_pause_resume = {
		void apply(inout bit<8> reg_val, out bit<8> rv){
			rv = reg_val;
			if(reg_val == PFC_GEN_REQ_PAUSE){
				reg_val = PFC_GEN_REQ_RESUME;
			}
			else{
				reg_val = PFC_GEN_REQ_PAUSE;
			}
		}
	};

	action toggle_get_pfc_pause_resume(){
		eg_meta.pfc_gen_req = toggle_read_pfc_pause_resume.execute(0);
	}
	#endif 

	#if DEBUG
	Register<bit<32>,bit<1>>(1,1) reg_pause_ts_idx;
	RegisterAction<bit<32>,bit<1>,bit<32>>(reg_pause_ts_idx) read_update_pause_ts_idx = {
		void apply(inout bit<32> reg_val, out bit<32> rv){
			rv = reg_val;

			if(reg_val < MAX_PKT_IPG_RECORDS){
				reg_val = reg_val + 1;
			}
		}
	};
	action get_next_pause_ts_idx(){
		eg_meta.pause_ts_idx = read_update_pause_ts_idx.execute(0);
	}

	Register<bit<32>,bit<1>>(1,1) reg_resume_ts_idx;
	RegisterAction<bit<32>,bit<1>,bit<32>>(reg_resume_ts_idx) read_update_resume_ts_idx = {
		void apply(inout bit<32> reg_val, out bit<32> rv){
			rv = reg_val;

			if(reg_val < MAX_PKT_IPG_RECORDS){
				reg_val = reg_val + 1;
			}
		}
	};
	action get_next_resume_ts_idx(){
		eg_meta.resume_ts_idx = read_update_resume_ts_idx.execute(0);
	}

	Register<bit<32>, bit<32>>(MAX_PFC_REQ_RECORDS) reg_pause_ts;
	Register<bit<32>, bit<32>>(MAX_PFC_REQ_RECORDS) reg_resume_ts;

	action record_pause_ts(){
		reg_pause_ts.write(eg_meta.pause_ts_idx, eg_intr_md_from_prsr.global_tstamp[31:0]);
	}

	action record_resume_ts(){
		reg_resume_ts.write(eg_meta.resume_ts_idx, eg_intr_md_from_prsr.global_tstamp[31:0]);
	}

	#endif
	// ##### PFC DELAY MEASUREMENT (end) #####

	// ##### BUFFER DRAIN RATE MEASUREMENT (start) #####
	#if DEBUG
	Register<bit<32>,bit<1>>(1,0) reg_qdepth_record_idx;
	RegisterAction<bit<32>,bit<1>,bit<32>>(reg_qdepth_record_idx) read_update_qdepth_record_idx = {
		void apply(inout bit<32> reg_val, out bit<32> rv){
			rv = reg_val;

			if(reg_val < MAX_QDEPTH_RECORDS){
				reg_val = reg_val + 1;
			}
		}
	};
	action get_next_qdepth_record_idx(){
		eg_meta.qdepth_record_idx = read_update_qdepth_record_idx.execute(0);
	}

	Register<qdepth_record_t, bit<32>>(MAX_QDEPTH_RECORDS) reg_qdepth_records;
	RegisterAction<qdepth_record_t, bit<32>, bit<32>>(reg_qdepth_records) write_qdepth_record = {
		void apply(inout qdepth_record_t reg_val, out bit<32> rv){
			reg_val.time = eg_intr_md_from_prsr.global_tstamp[31:0];
			reg_val.qdepth = (bit<32>) eg_intr_md.deq_qdepth;
		}
	};

	action insert_qdepth_record(){
		write_qdepth_record.execute(eg_meta.qdepth_record_idx);
	}
	#endif
	// ##### BUFFER DRAIN RATE MEASUREMENT (end) #####

	apply{
		
		debug_count();
		// check if this is a lack update packet
		if(eg_meta.ig_mirror_lack_update.isValid()){ //  eg_intr_md.egress_port == 68
			get_leading_ack_notify_max_count.apply(); // sets eg_meta.leading_ack_notify_max_count
			set_leading_ack_notify_max_count(); // sets max count in reg_leading_ack_notify_count
			record_leading_ack();
			record_leading_ack_era();
			drop();
			eg_debug_counter.count(6);
			// exit;
		}
		else if(eg_meta.ig_mirror_loss_notification.isValid()){ 
			if(eg_intr_md.egress_rid == PAUSE_FRAME_MCAST_RID){
				// pkt copy for creating PFC/PAUSE frame

				// OLD: ----- PAUSE FRAME -----
				// add_ethernet_pause_hdr();
				// add_pause_quanta.apply();
				// -----------------------------

				// ------ PFC FRAME ------
				add_ethernet_pfc_hdr();
				add_pfc_c1_quanta.apply();
				// -----------------------
			}
			else { // pkt copy for creating loss notification
				// NOTE: do NOT update lack and lack_era
				add_lack_loss_notification_hdrs();
				copy_data_to_loss_notification_hdrs();
				// BUG FIX: to avoid stale LACK after loss notification
				set_leading_ack_notify_max_count_to_zero();
			}
		}
		// OLD logic: PFC pause/resume using mirroring
		/* else if (eg_meta.eg_mirror_pfc_pkt.isValid()){
			eg_debug_counter.count(2);
			add_ethernet_pfc_hdr();
			copy_pfc_c1_quanta();
		} */
		else if (eg_meta.either_rx_buffered_or_timer_pfc == 1){
			if(hdr.linkradar_rx_buffered.isValid()){ // rx buffered

				// -------------- Normal Processing ----------------
				check_recirc_buffer_pfc_pause_threshold(); // sets eg_meta.exceeded_recirc_buffer_pfc_pause_threshold
				check_recirc_buffer_pfc_resume_threshold(); // sets eg_meta.subceeded_recirc_buffer_pfc_resume_threshold

				if(eg_meta.exceeded_recirc_buffer_pfc_pause_threshold == 1){

					check_update_pfc_pause_state(); // fills eg_meta.should_send_pfc_pause
					
					if(eg_meta.should_send_pfc_pause == 1){
						// mirror_to_generate_pfc_frame(MAX_PFC_QUANTA); // max for pause
						schedule_to_generate_pfc_pause(); 
						eg_debug_counter.count(0);
					}
				}
				else if(eg_meta.subceeded_recirc_buffer_pfc_resume_threshold == 1){

					check_update_pfc_resume_state(); // fills eg_meta.should_send_pfc_resume
					
					if(eg_meta.should_send_pfc_resume == 1){
						// mirror_to_generate_pfc_frame(0); // zero for resume
						schedule_to_generate_pfc_resume();
						eg_debug_counter.count(1);
					}
				}

				#if DEBUG
				// -------- Experimental Measurement -----------
					get_next_qdepth_record_idx();
					insert_qdepth_record();
				// ---------------------------------------------
				#endif
			} // end of if rx_buffered
			else { // this MUST be for timer PFC pkts
				#if MEASURE_PFC_DELAYS
				toggle_get_pfc_pause_resume(); // reads into eg_meta.pfc_gen_req 
				if(eg_meta.pfc_gen_req == PFC_GEN_REQ_PAUSE){
					get_next_pause_ts_idx();
					record_pause_ts(); 
					transform_pfc_gen_to_pause();
				}
				else if(eg_meta.pfc_gen_req == PFC_GEN_REQ_RESUME){
					get_next_resume_ts_idx();
					record_resume_ts();
					transform_pfc_gen_to_resume();
				}
				else{
					drop();
				}

				#else  // normal processing
				// check_reset_pfc_gen_req(); // reads into eg_meta.pfc_gen_req
				check_reset_pfc_gen_req.apply();
				gen_pfc_or_drop.apply(); // takes action based on eg_meta.pfc_gen_req

				#if DEBUG  // for PFC algo debugging
				if(eg_meta.pfc_gen_req == PFC_GEN_REQ_PAUSE){
					get_next_pause_ts_idx();
					record_pause_ts(); 
				}
				else if(eg_meta.pfc_gen_req == PFC_GEN_REQ_RESUME){
					get_next_resume_ts_idx();
					record_resume_ts();
				}
				#endif  // end of if DEBUG
				
				#endif // end of MEASURE_PFC_DELAYS if-else
			
			}
		}
		else{ // normal or lack/courier packets

			// #### ECN Marking  ######
			/* if(hdr.ipv4.ecn == 0b01 || hdr.ipv4.ecn == 0b10){
				check_ecn_marking_threshold(); // fills eg_meta.exceeded_ecn_marking_threshold
				if(eg_meta.exceeded_ecn_marking_threshold == 1){
					mark_ecn_ce_codepoint();
				}
			} */
			// #### ECN Marking (end) ######
			
			// LOGIC: retrieve these into the lack hdr first. 
			// Later decide if we want to add the lack hdr
			retrieve_leading_ack();
			retrieve_leading_ack_era();

			// LOGIC: only setting meta. Doesn't affect normal pkts.
			get_courier_pkt_mirror_session.apply(); // sets eg_meta.mirror_session

			check_if_lack_pending(); // set eg_meta.is_lack_pending

			// LOGIC: adding lack hdr might be redundant if it is a courier packet
			// But it doesn't matter. Simplifies the code flow. 
			add_lack_hdr_or_drop_mirror_courier_pkt.apply();

			
			
		}
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
