#!/bin/bash

mydir=$(dirname $0)

conda run -n lg-data-analysis python3 $mydir/display_combined_result.py


