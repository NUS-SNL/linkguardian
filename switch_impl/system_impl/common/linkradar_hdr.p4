#ifndef _LINKRADAR_HDR_
#define _LINKRADAR_HDR_

const int MAX_PORTS = 256;
const int MAX_PROTECTED_PORTS = 16;
const int MAX_SEQ_NUMBERS = 65536;
const int SEQ_NUMBERS_HALF_RANGE = 32768;
const int MAX_SEQ_NO = 65535;
const int LEADING_ACK_NOTIFY_COUNT = 1;
const int INVALID_SEQ_NUMBER = 99999; // used for initialization

const int RETX_QID = 2;

typedef bit<16> seq_no_t;
typedef bit<2> linkradar_hdr_type_t;

const linkradar_hdr_type_t LINKRADAR_HDR_TYPE_DATA = 0b00;
const linkradar_hdr_type_t LINKRADAR_HDR_TYPE_LACK = 0b01;
const linkradar_hdr_type_t LINKRADAR_HDR_TYPE_LACK_LOSS_NOTIFY = 0b10;
const linkradar_hdr_type_t LINKRADAR_HDR_TYPE_TX_BUFFERED = 0b11;


#define LINKRADAR_COMMON_HDR \
    linkradar_hdr_type_t type

// header linkradar_common_h {
//     LINKRADAR_COMMON_HDR;
// }

header linkradar_data_h { // V IMP: PLEASE CHANGE CORRESPONDING SCAPY FILE!!
    LINKRADAR_COMMON_HDR; // 2 bits <== MUST be the first 2 bits for lookahead
    bit<1> _pad;
    bit<1> era;
    bit<1> reTx;
    bit<1> dummy; // to distinguish dummy pkts vs normal data pkts
    bit<1> blocking_mode;
    bit<1> rx_buffered;
    seq_no_t seq_no;
}

// IMP: linkradar_lack_h should exactly be the 
// beginning of linkradar_loss_notification_h
// any change here should reflect in linkradar_loss_notification_h
header linkradar_lack_h {
    LINKRADAR_COMMON_HDR; // 2 bits
    bit<1> is_piggy_backed;
    bit<1> era;
    bit<4> _pad;
    seq_no_t leading_ack;
}

header linkradar_loss_notification_h {
    bit<8> hole_size; 
    seq_no_t first_lost_seq_no;
}

// ***********  Sender-specific  ***********

header linkradar_buffered_h {
    LINKRADAR_COMMON_HDR; // 2 bits
    bit<5> _pad_count;
    PortId_t dst_eg_port; // 9 bits
}

// ***********  Receiver-specific  ***********

header linkradar_rx_buffered_h {
    bit<8> orig_ig_port;
}

#endif
