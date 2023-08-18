#!/usr/bin/env python3

import pandas as pd

base_path = '~/traces/fct_expt_tcp'
expt_names = ['10-3', '10-3_lg', '10-3_lg_nb']

summary_dfs = []

for expt_name in expt_names:
    pkl_file = base_path + '/' + expt_name + '/24387B_fct_combined-summary.pkl'
    summary_df = pd.read_pickle(pkl_file)
    summary_df = summary_df.rename(columns={'fct1': expt_name})
    summary_dfs.append(summary_df)

concat_list = []

for i in range(len(summary_dfs)):
    concat_list.append(summary_dfs[i][[expt_names[i]]])

combined_result = pd.concat(concat_list, axis=1)

print(combined_result)

