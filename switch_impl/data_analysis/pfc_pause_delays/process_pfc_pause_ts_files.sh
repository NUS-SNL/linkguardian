#!/bin/bash



# For PFC pause delays
tail -n +2 100g_pfc_delay_ts_run1.dat | awk '{printf("%d\n",$2-$1)}' | awk '{if ($1 <0) print $1+4294967296; else print $1}' > 100g_pfc_pause_delays.dat
for run in {2..10};do tail -n +2 100g_pfc_delay_ts_run${run}.dat | awk '{printf("%d\n",$2-$1)}' | awk '{if ($1 <0) print $1+4294967296; else print $1}' >> 100g_pfc_pause_delays.dat ; done


# For PFC resume delays
tail -n +2 100g_pfc_delay_ts_run1.dat | awk '{printf("%d\n",$4-$3)}' | awk '{if ($1 <0) print $1+4294967296; else print $1}' > 100g_pfc_resume_delays.dat
for run in {2..10};do tail -n +2 100g_pfc_delay_ts_run${run}.dat | awk '{printf("%d\n",$4-$3)}' | awk '{if ($1 <0) print $1+4294967296; else print $1}' >> 100g_pfc_resume_delays.dat ; done


# For PFC pause delays
tail -n +2 25g_pfc_delay_ts_run1.dat | awk '{printf("%d\n",$2-$1)}' | awk '{if ($1 <0) print $1+4294967296; else print $1}' > 25g_pfc_pause_delays.dat
for run in {2..10};do tail -n +2 25g_pfc_delay_ts_run${run}.dat | awk '{printf("%d\n",$2-$1)}' | awk '{if ($1 <0) print $1+4294967296; else print $1}' >> 25g_pfc_pause_delays.dat ; done


# For PFC resume delays
tail -n +2 25g_pfc_delay_ts_run1.dat | awk '{printf("%d\n",$4-$3)}' | awk '{if ($1 <0) print $1+4294967296; else print $1}' > 25g_pfc_resume_delays.dat
for run in {2..10};do tail -n +2 25g_pfc_delay_ts_run${run}.dat | awk '{printf("%d\n",$4-$3)}' | awk '{if ($1 <0) print $1+4294967296; else print $1}' >> 25g_pfc_resume_delays.dat ; done




# For PFC pause delays
tail -n +2 10g_pfc_delay_ts_run1.dat | awk '{printf("%d\n",$2-$1)}' | awk '{if ($1 <0) print $1+4294967296; else print $1}' > 10g_pfc_pause_delays.dat
for run in {2..5};do tail -n +2 10g_pfc_delay_ts_run${run}.dat | awk '{printf("%d\n",$2-$1)}' | awk '{if ($1 <0) print $1+4294967296; else print $1}' >> 10g_pfc_pause_delays.dat ; done


# For PFC resume delays
tail -n +2 10g_pfc_delay_ts_run1.dat | awk '{printf("%d\n",$4-$3)}' | awk '{if ($1 <0) print $1+4294967296; else print $1}' > 10g_pfc_resume_delays.dat
for run in {2..5};do tail -n +2 10g_pfc_delay_ts_run${run}.dat | awk '{printf("%d\n",$4-$3)}' | awk '{if ($1 <0) print $1+4294967296; else print $1}' >> 10g_pfc_resume_delays.dat ; done


