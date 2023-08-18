set terminal pdf size 1.5,0.8 font ",8"

set output "../../figure16b.pdf"

load "../gnuplot_common.gp"

max_paths_per_tor = 192
max_capacity_per_pod = 19200

## NEEDS MANUAL ADJUSTMENT ##
# margins to cut out white space
set lmargin 7
set tmargin 0.5

set yrange [0.88:1]
set xrange [0:0.25]

set xlabel "Decrease in Least Capacity\nper Pod (normalized %)" offset "0,1"
# set logscale x
# set format x "10^{%T}"
# set xtics 1e1 font ",7"

set ylabel "CDF" offset 2,0
# set ytics 0.2 font ",7"

set key bottom right

plot '../../../output_files/sigcomm23_eval/diff_min_pod_capacity_50_cdf.dat' u (($1/max_capacity_per_pod)*100):4 with l ls 1 title "50%",\
	 '../../../output_files/sigcomm23_eval/diff_min_pod_capacity_75_cdf.dat' u (($1/max_capacity_per_pod)*100):4 with l ls 1 dt "-" title "75%",\
