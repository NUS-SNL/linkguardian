#!/bin/bash

mydir=$(dirname $0)

source $mydir/../common/bash_common.sh

data_dir=~/traces/fct_expt_rdma

paste $data_dir/10-3-summary.dat $data_dir/10-3_lg-summary.dat $data_dir/10-3_lg_nb-summary.dat | awk 'BEGIN{OFS=" "} {if(NR==1){printf("--- No_Protection LinkGuardian LinkGuardianNB\n")} else {print $1,$2,$4,$6}}' | column -t