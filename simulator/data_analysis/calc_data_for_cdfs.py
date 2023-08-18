#!/usr/bin/env python3

import sys
import os
import re
import csv
import pandas as pd
from termcolor import colored

sys.path.append("../")
from utils.lg_logging import *


# checking arguments
if len(sys.argv) != 3:
    print(colored("Usage:",'yellow') + " {} <corropt_dat_file> <lg_corropt_dat_file>".format(sys.argv[0]))
    sys.exit(1)

corropt_data_file = sys.argv[1]
lg_corropt_data_file = sys.argv[2]

corropt_file_name = os.path.basename(corropt_data_file)
lg_corropt_file_name = os.path.basename(lg_corropt_data_file)

match_obj_corropt = re.search(r"_([0-9]{2}).dat", corropt_file_name) # match exactly 2 digits
match_obj_lg_corropt = re.search(r"_([0-9]{2}).dat", lg_corropt_file_name) # match exactly 2 digits

if match_obj_corropt == None or match_obj_lg_corropt == None:
    print(TERM_ERROR_STR + "Could not extract the capacity constraint from the file names")
    print("The data files should end with \"_<capacity constraint>.dat\"")
    sys.exit(1)

capacity_constraint_corropt = match_obj_corropt.groups()[0]
capacity_constraint_lg_corropt = match_obj_lg_corropt.groups()[0]


if capacity_constraint_corropt != capacity_constraint_lg_corropt:
    print(TERM_ERROR_STR + "The two capacity constraints {} and {} do not match".format(capacity_constraint_corropt, capacity_constraint_lg_corropt))
    print("Please specify correct data files with same capacity constraints")
    sys.exit(1)
    
# prepare the outfiles
output_dir = os.path.dirname(corropt_data_file)
total_penalty_ratio_outfile = output_dir + "/" + "total_penalty_ratio_{}.dat".format(capacity_constraint_corropt)
total_penalty_ratio_cdf_outfile = output_dir + "/" + "total_penalty_ratio_{}_cdf.dat".format(capacity_constraint_corropt)
diff_min_pod_capacity_outfile = output_dir + "/" + "diff_min_pod_capacity_{}.dat".format(capacity_constraint_corropt)
diff_min_pod_capacity_cdf_outfile = output_dir + "/" + "diff_min_pod_capacity_{}_cdf.dat".format(capacity_constraint_corropt)


####################
# Helper Functions #
####################

def get_typed_row(row):
    return [int(row[0]), float(row[1]), float(row[2]), float(row[3]),\
            int(row[4]), float(row[5]), float(row[6]), float(row[7]),
            int(row[8]), int(row[9]), int(row[10])]

def get_df_from_sim_datafile(data_file) -> pd.DataFrame:
    
    csvreader = csv.reader(open(data_file, 'r'), delimiter='\t')

    header = next(csvreader)
    rows = []
    
    prev = next(csvreader) # read the first row
    rows.append(get_typed_row(prev))
    
    skipped_count = 0

    for row in csvreader:
        curr = row
        if curr[1:] == prev[1:]:
            skipped_count += 1
        else:
            rows.append(get_typed_row(curr))
        prev = curr

    list_data = []
    list_data.extend(rows)
    df = pd.DataFrame(list_data, columns=header)

    return df

########################
# Actual Data Analysis #
########################

required_cols = ['time', 'total_effective_penalty', 'min_per_pod_capacity']

# get the data into data frames without the duplicates
# sim data has duplicates to make graphs look proper
df_corropt = get_df_from_sim_datafile(corropt_data_file)
df_lg_corropt = get_df_from_sim_datafile(lg_corropt_data_file)

# get only the required cols from the data frames
df_corropt = df_corropt[required_cols]
df_lg_corropt = df_lg_corropt[required_cols]


# rename to cols to avoid name clash
cols_rename_dict_corropt = {'time': 'time_corropt', 'total_effective_penalty': 'total_effective_penalty_corropt' ,\
                            'min_per_pod_capacity':'min_per_pod_capacity_corropt'}
cols_rename_dict_lg_corropt = {'time': 'time_lg_corropt', 'total_effective_penalty': 'total_effective_penalty_lg_corropt' ,\
                               'min_per_pod_capacity':'min_per_pod_capacity_lg_corropt'}
df_corropt = df_corropt.rename(columns=cols_rename_dict_corropt)
df_lg_corropt = df_lg_corropt.rename(columns=cols_rename_dict_lg_corropt)



print("Running data correctness checks...")

if len(df_corropt) == len(df_lg_corropt):
    print("Both data files have the same number of rows ({}) (as expected)!".format(len(df_corropt)))
else:
    print("Something is wrong. The 2 files don't have the same number of rows ({} and {})..."\
          .format(len(df_corropt), len(df_lg_corropt)))
    sys.exit(1)
    

# combine the two data frames column-wise
combined_df = pd.concat([df_corropt, df_lg_corropt], axis=1)

# check that the 2 time cols match exactly with each other
diff_time_df = combined_df.query("time_corropt != time_lg_corropt")
if len(diff_time_df) == 0:
    print("Times from both the datasets match perfectly (as expected)")
else:
    print("Something is wrong. Times from both the datasets do not match")
    sys.exit(1)

# compute the total penalty ratio column
combined_df["total_penalty_ratio"] = combined_df["total_effective_penalty_corropt"] / combined_df["total_effective_penalty_lg_corropt"]

# compute the relative loss in min pod capacity
combined_df["diff_min_pod_capacity"] = combined_df["min_per_pod_capacity_corropt"] - combined_df["min_per_pod_capacity_lg_corropt"]


# filter and get exactly 1 year data
# exclude the initial -4 days offset that we added
one_year_df = combined_df.query("time_corropt >= 345600 and time_corropt <= 31881600")

# dump the data to respective files
one_year_df[["total_penalty_ratio"]].to_csv(total_penalty_ratio_outfile, sep="\t", quoting=csv.QUOTE_NONE, index=False, header=False)
one_year_df[["diff_min_pod_capacity"]].to_csv(diff_min_pod_capacity_outfile, sep="\t", quoting=csv.QUOTE_NONE, index=False, header=False)

# compute CDFs
cdf_cmd = "./getcdf {} > {}".format(total_penalty_ratio_outfile, total_penalty_ratio_cdf_outfile)
os.system(cdf_cmd)
cdf_cmd = "./getcdf {} > {}".format(diff_min_pod_capacity_outfile, diff_min_pod_capacity_cdf_outfile)
os.system(cdf_cmd)

print(colored("Output files:", "yellow"))
print(total_penalty_ratio_outfile)
print(total_penalty_ratio_cdf_outfile)
print(diff_min_pod_capacity_outfile)
print(diff_min_pod_capacity_cdf_outfile)
