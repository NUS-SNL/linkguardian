#!/bin/bash

my_dir="$(dirname "$0")"

$my_dir/analyze_expt_data.sh 10-3_lg 1 $my_dir
echo ""
$my_dir/analyze_expt_data.sh 10-3_lg_nb 0 $my_dir


