#!/home/raj/miniconda3/envs/research/bin/python3

import sys
import os
import csv
import pandas

# TODO: add args parsing to allow option to specify column header presence

if len(sys.argv) != 2:
    print("Usage: {} <single col dat file>".format(sys.argv[0]))
    sys.exit(1)

datfile = sys.argv[1]
outfile = os.path.splitext(datfile)[0] + "-summary.dat"

df = pandas.read_csv(datfile, header=None)


df_summary = df.describe(percentiles=[.5, .9, .95, .99, .999, .9999,.99999], include='all')
df_summary = df_summary.round(3)
df_summary = df_summary.reindex(["min","mean","50%","90%","95%","99%","99.9%","99.99%","99.999%","max","std","count"])

df_summary.to_csv(outfile, sep="\t", quoting=csv.QUOTE_NONE)

print("Descriptive stats: {}".format(outfile))
