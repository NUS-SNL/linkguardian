#!/usr/bin/env python3

import pandas as pd

base_path = '~/traces/fct_expt_tcp'
expt_names = ['10-3', '10-3_lg', '10-3_lg_nb']
readable_expt_names = {'10-3':'No_Protection', '10-3_lg':'LinkGuardian', '10-3_lg_nb':'LinkGuardianNB'}

summary_dfs = []

for expt_name in expt_names:
    pkl_file = base_path + '/' + expt_name + '/24387B_fct_combined-summary.pkl'
    summary_df = pd.read_pickle(pkl_file)
    col_name = readable_expt_names[expt_name]
    summary_df = summary_df.rename(columns={'fct1': col_name})
    summary_dfs.append(summary_df)

concat_list = []

for i in range(len(summary_dfs)):
    col_name = readable_expt_names[expt_names[i]]
    concat_list.append(summary_dfs[i][[col_name]])

combined_result = pd.concat(concat_list, axis=1)

print(combined_result)

