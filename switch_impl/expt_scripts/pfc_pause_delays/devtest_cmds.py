ipg_outfile = "/home/cirlab/jarvis-tofino/linkradar/expt-data/evaluation/pfc_pause_delays/10g_normal_ipg.dat"
pfc_delay_ts_outfile_prefix = "/home/cirlab/jarvis-tofino/linkradar/expt-data/evaluation/pfc_pause_delays/10g_pfc_delay_runs/10g_pfc_delay_ts"
MAX_PKT_IPG_RECORDS = 70000
UNINT32_MAX = pow(2, 32) - 1

reg_pkt_ipg_record_idx = bfrt.receiver.pipe.SwitchIngress.reg_pkt_ipg_record_idx
reg_pkt_ipg_records = bfrt.receiver.pipe.SwitchIngress.reg_pkt_ipg_records
reg_prev_ts = bfrt.receiver.pipe.SwitchIngress.reg_prev_ts

reg_pause_ts_idx = bfrt.receiver.pipe.SwitchEgress.reg_pause_ts_idx
reg_resume_ts_idx = bfrt.receiver.pipe.SwitchEgress.reg_resume_ts_idx
reg_pause_ts = bfrt.receiver.pipe.SwitchEgress.reg_pause_ts
reg_resume_ts = bfrt.receiver.pipe.SwitchEgress.reg_resume_ts
reg_pfc_toggle = bfrt.receiver.pipe.SwitchEgress.reg_pfc_toggle

def reset_all_pfc_measurement_state():
    reg_pkt_ipg_record_idx.clear()
    reg_pkt_ipg_records.clear()
    reg_prev_ts.clear()
    reg_pause_ts_idx.clear()
    reg_resume_ts_idx.clear()
    reg_pause_ts.clear()
    reg_resume_ts.clear()
    reg_pfc_toggle.clear()

ipg_list = []

def get_ipg_values(ipg_list):
    for i in range(1, MAX_PKT_IPG_RECORDS):
        prev_ts = reg_pkt_ipg_records.get(REGISTER_INDEX=i, from_hw=1, print_ents=0).data[b'SwitchIngress.reg_pkt_ipg_records.prev_ts'][0]
        curr_ts = reg_pkt_ipg_records.get(REGISTER_INDEX=i, from_hw=1, print_ents=0).data[b'SwitchIngress.reg_pkt_ipg_records.curr_ts'][0]

        ipg = curr_ts - prev_ts
        if ipg < 0:  # wrap around. Correct it.
            ipg = ipg + UNINT32_MAX + 1

        ipg_list.append(ipg)


def dump_append_ipg_values(ipg_list):
    with open(ipg_outfile, "a") as fout:
        for ipg in ipg_list:
            fout.write("{}\n".format(ipg))



""" print(reg_pause_ts.get(REGISTER_INDEX=1, from_hw=1, print_ents=0).data)
print(reg_pkt_ipg_records.get(REGISTER_INDEX=1, from_hw=1, print_ents=0).data)
print(reg_resume_ts.get(REGISTER_INDEX=1, from_hw=1, print_ents=0).data) """


pfc_delay_ts_list = []

def get_pfc_delay_ts():
    global pfc_delay_ts_list
    pfc_delay_ts_list = []

    for i in range(1, MAX_PKT_IPG_RECORDS):
        prev_ts = reg_pkt_ipg_records.get(REGISTER_INDEX=i, from_hw=1, print_ents=0).data[b'SwitchIngress.reg_pkt_ipg_records.prev_ts'][0]
        curr_ts = reg_pkt_ipg_records.get(REGISTER_INDEX=i, from_hw=1, print_ents=0).data[b'SwitchIngress.reg_pkt_ipg_records.curr_ts'][0]
        pause_ts = reg_pause_ts.get(REGISTER_INDEX=i, from_hw=1, print_ents=0).data[b'SwitchEgress.reg_pause_ts.f1'][0]
        resume_ts = reg_resume_ts.get(REGISTER_INDEX=i, from_hw=1, print_ents=0).data[b'SwitchEgress.reg_resume_ts.f1'][0]

        pfc_delay_ts_list.append((pause_ts, prev_ts, resume_ts, curr_ts))

    
def dump_pfc_delay_ts_values(pfc_delay_ts_list, run):
    pfc_delay_ts_outfile = pfc_delay_ts_outfile_prefix + "_run{}.dat".format(run)
    with open(pfc_delay_ts_outfile, "w") as fout:
        # Add the column headers first
        fout.write("pause_ts\tprev_ts\tresume_ts\tcurr_ts\n")
        for ts_entry in pfc_delay_ts_list:
            fout.write("{}\t{}\t{}\t{}\n".format(*ts_entry))

