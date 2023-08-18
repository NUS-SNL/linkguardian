#!/usr/bin/env python3

import sys
import os
import csv
import glob
import pandas as pd
from termcolor import colored

# checking arguments
if len(sys.argv) != 3:
    print(colored("Usage:",'yellow') + " {} <target_dir_path> <flowsize in B>".format(sys.argv[0]))
    sys.exit(1)

TARGET_DIR = sys.argv[1]
flow_size = sys.argv[2]

my_dir = os.path.dirname(os.path.realpath(__file__))
getcdf_script = my_dir + "/../common/getcdf"

sender_dat_files = glob.glob("{}/{}B_sender_run*.dat".format(TARGET_DIR, flow_size))

print(colored("*** Found {} runs".format(len(sender_dat_files)), 'yellow'))
      
fct_data_frames = []

for run_file in sender_dat_files:
    df = pd.read_csv(run_file, delimiter='\t')
    fct_data_frames.append(df)


sum_of_rows = 0
for df in fct_data_frames:
    sum_of_rows += len(df.index)
    
# print("Sum of rows: {}".format(sum_of_rows))

fct_data = pd.concat(fct_data_frames, ignore_index=True)

print("Total rows in concat data: {}".format(len(fct_data.index)))

########  NO NEED OF RTT CALCULATIONS SINCE NOT USING FCT-2 ANYMORE ########

# rtt1 = fct_data["firstAckTs"] - fct_data["firstDataTs"]
# rtt2 = fct_data["lastAckTs"] - fct_data["lastDataTs"]

# rtt1_stats = rtt1.describe(percentiles=[.5, .9, .95, .99, .9999], include='all')
# # rtt1_stats = rtt1_stats.round(3)
# print(colored("*** RTT-1 Statistics", 'yellow'))
# print(rtt1_stats)

# rtt2_stats = rtt2.describe(percentiles=[.5, .9, .95, .99, .9999], include='all')
# # rtt2_stats = rtt2_stats.round(3)
# print(colored("*** RTT-2 Statistics", 'yellow'))
# print(rtt2_stats)

# rtt_to_use = rtt1_stats["mean"] * 1000000
# rtt_to_use = round(rtt_to_use)
# print(colored("*** Using mean of RTT-1 for FCT-2: {}us".format(rtt_to_use), 'yellow'))


# FCT1: from first data pkt to last ack pkt
fct1 = (fct_data["lastAckTs"] - fct_data["firstDataTs"]) * 1000000
fct1 = fct1.round(3)

# FCT2: from first data pkt to last data pkt + RTT/2
# fct2 = (fct_data["lastDataTs"] - fct_data["firstDataTs"]) * 1000000  + (rtt_to_use/2)
# fct2 = fct2.round(3)


# Appending fct1 and fct2 to the overall dataframe
fct_data["fct1"] = fct1
# fct_data["fct2"] = fct2

################
# UNAFFECTED FCT 
################
fct_data_unaffected = fct_data.query('affected == 0')[["fct1"]] # , "fct2"]] # already rounded to 3 decimals


fct_unaffected_summary = fct_data_unaffected.describe(percentiles=[.5, .9, .95, .99, .999, .9999,.99999], include='all')
fct_unaffected_summary = fct_unaffected_summary.round(3)
fct_unaffected_summary = fct_unaffected_summary.reindex(["min","mean","50%","90%","95%","99%","99.9%","99.99%","99.999%","max","std","count"])

fct1_unaffected_outfile = "{}/{}B_fct_unaffected.dat".format(TARGET_DIR, flow_size)
fct1_unaffected_cdf_outfile = "{}/{}B_fct_unaffected_cdf.dat".format(TARGET_DIR, flow_size)
# fct2_unaffected_outfile = "{}/{}B_fct2_unaffected.dat".format(TARGET_DIR, flow_size)
fct_unaffected_summary_outfile = "{}/{}B_fct_unaffected-summary.dat".format(TARGET_DIR, flow_size)

# print(colored("*** Output files for unaffected FCT:", 'yellow'))
# print(fct1_unaffected_outfile)
# print(fct1_unaffected_cdf_outfile)
# # print(fct2_unaffected_outfile)
# print(fct_unaffected_summary_outfile)

fct_data_unaffected[["fct1"]].to_csv(fct1_unaffected_outfile, sep="\t", quoting=csv.QUOTE_NONE, index=False, header=False)
os.system("{} {} > {}".format(getcdf_script, fct1_unaffected_outfile, fct1_unaffected_cdf_outfile))
# fct_data_unaffected[["fct2"]].to_csv(fct2_unaffected_outfile, sep="\t", quoting=csv.QUOTE_NONE, index=False, header=False)
fct_unaffected_summary.to_csv(fct_unaffected_summary_outfile, sep="\t", quoting=csv.QUOTE_NONE)


################
# AFFECTED FCT 
################
fct_data_affected = fct_data.query('affected == 1')[["fct1"]] # , "fct2"]] # already rounded to 3 decimals
fct_affected_summary = fct_data_affected.describe(percentiles=[.5, .9, .95, .99, .999, .9999,.99999], include='all')
fct_affected_summary = fct_affected_summary.round(3)
fct_affected_summary = fct_affected_summary.reindex(["min","mean","50%","90%","95%","99%","99.9%","99.99%","99.999%","max","std","count"])

fct1_affected_outfile = "{}/{}B_fct_affected.dat".format(TARGET_DIR, flow_size)
fct1_affected_cdf_outfile = "{}/{}B_fct_affected_cdf.dat".format(TARGET_DIR, flow_size)
# fct2_affected_outfile = "{}/{}B_fct2_affected.dat".format(TARGET_DIR, flow_size)
fct_affected_summary_outfile = "{}/{}B_fct_affected-summary.dat".format(TARGET_DIR, flow_size)

# print(colored("*** Output files for affected FCT:", 'yellow'))
# print(fct1_affected_outfile)
# print(fct1_affected_cdf_outfile)
# # print(fct2_affected_outfile)
# print(fct_affected_summary_outfile)

fct_data_affected[["fct1"]].to_csv(fct1_affected_outfile, sep="\t", quoting=csv.QUOTE_NONE, index=False, header=False)
os.system("{} {} > {}".format(getcdf_script, fct1_affected_outfile, fct1_affected_cdf_outfile))
# fct_data_affected[["fct2"]].to_csv(fct2_affected_outfile, sep="\t", quoting=csv.QUOTE_NONE, index=False, header=False)
fct_affected_summary.to_csv(fct_affected_summary_outfile, sep="\t", quoting=csv.QUOTE_NONE)

#######################################################
# Combined (overall) FCT-1 FCT-2 and their summaries
#######################################################
# The erroneous affected flows (affected == 2) are exluded here
# since we combine the baseline and the affected data only

fct_data_combined = pd.concat([fct_data_unaffected, fct_data_affected], ignore_index=True)
fct_combined_summary = fct_data_combined.describe(percentiles=[.5, .9, .95, .99, .999, .9999,.99999], include='all')
fct_combined_summary = fct_combined_summary.round(3)
fct_combined_summary = fct_combined_summary.reindex(["min","mean","50%","90%","95%","99%","99.9%","99.99%","99.999%","max","std","count"])

fct1_combined_outfile = "{}/{}B_fct_combined.dat".format(TARGET_DIR, flow_size)
fct1_combined_cdf_outfile = "{}/{}B_fct_combined_cdf.dat".format(TARGET_DIR, flow_size)
# fct2_combined_outfile = "{}/{}B_fct2_combined.dat".format(TARGET_DIR, flow_size)
fct_combined_summary_outfile = "{}/{}B_fct_combined-summary.dat".format(TARGET_DIR, flow_size)
fct_combined_summary_pickle = "{}/{}B_fct_combined-summary.pkl".format(TARGET_DIR, flow_size)

print(colored("*** Output files for overall FCT:", 'yellow'))
print(fct1_combined_outfile)
print(fct1_combined_cdf_outfile)
# print(fct2_combined_outfile)
print(fct_combined_summary_outfile)
print(fct_combined_summary_pickle)

fct_data_combined[["fct1"]].to_csv(fct1_combined_outfile, sep="\t", quoting=csv.QUOTE_NONE, index=False, header=False)
os.system("{} {} > {}".format(getcdf_script, fct1_combined_outfile, fct1_combined_cdf_outfile))
# fct_data_combined[["fct2"]].to_csv(fct2_combined_outfile, sep="\t", quoting=csv.QUOTE_NONE, index=False, header=False)
fct_combined_summary.to_csv(fct_combined_summary_outfile, sep="\t", quoting=csv.QUOTE_NONE)
fct_combined_summary.to_pickle(fct_combined_summary_pickle)


################################################################
# FCT-1 and FCT-2 COMBINED SUMMARIES: unaffected + affected
################################################################
fct1_summary = pd.concat([fct_unaffected_summary[["fct1"]].rename(columns={"fct1":"Unaffected"}), fct_affected_summary[["fct1"]].rename(columns={"fct1":"Affected"})], axis=1)
# fct2_summary = pd.concat([fct_unaffected_summary[["fct2"]].rename(columns={"fct2":"Unaffected"}), fct_affected_summary[["fct2"]].rename(columns={"fct2":"Affected"})], axis=1)

fct1_summary_outfile = "{}/{}B_fct-summary.dat".format(TARGET_DIR, flow_size)
# fct2_summary_outfile = "{}/{}B_fct2_summary.dat".format(TARGET_DIR, flow_size)

# print(colored("*** Output file(s) for unaffected/affected FCT summaries together:", 'yellow'))
# print(fct1_summary_outfile)
# # print(fct2_summary_outfile)

fct1_summary.to_csv(fct1_summary_outfile, sep='\t', quoting=csv.QUOTE_NONE)
# fct2_summary.to_csv(fct2_summary_outfile, sep='\t', quoting=csv.QUOTE_NONE)
