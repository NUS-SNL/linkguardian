#!/home/sigcomm23ae/miniconda3/envs/lg-data-analysis/bin/python3

import sys
import os
import csv
import pandas

# TODO: add args parsing to allow option to specify column header presence

if len(sys.argv) != 2 and len(sys.argv) != 3:
    print("Usage: {} <single col dat file> [col_name]".format(sys.argv[0]))
    sys.exit(1)

datfile = sys.argv[1]
col_name = None
if len(sys.argv) == 3:
    col_name = sys.argv[2]
outfile = os.path.splitext(datfile)[0] + "-summary.dat"

df = pandas.read_csv(datfile, header=None)


df_summary = df.describe(percentiles=[.5, .9, .95, .99, .999, .9999,.99999], include='all')
df_summary = df_summary.round(3)
df_summary = df_summary.reindex(["min","mean","50%","90%","95%","99%","99.9%","99.99%","99.999%","max","std","count"])

if col_name is not None:
    df_summary = df_summary.rename(columns={0: col_name})

df_summary.to_csv(outfile, sep="\t", quoting=csv.QUOTE_NONE)

print("Descriptive stats: {}".format(outfile))
