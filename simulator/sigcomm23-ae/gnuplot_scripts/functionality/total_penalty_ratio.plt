set terminal pdf size 1.5,0.8 font ",8"

set output "../../figure16a.pdf"

load "../gnuplot_common.gp"

max_paths_per_tor = 192
max_capacity_per_pod = 19200

## NEEDS MANUAL ADJUSTMENT ##
# margins to cut out white space
set lmargin 5.5
set rmargin 1

set xlabel "Gain in Total Penalty (x times)"
set logscale x
set format x "10^{%T}"
set xtics 1e1 font ",7"

set ylabel "CDF" offset 2,0
set ytics 0.2 font ",7"

set key top left reverse

plot '../../../output_files/sigcomm23_eval/total_penalty_ratio_50_cdf.dat' u 1:4 with l ls 3 title "50%",\
	#  '../../../output_files/sigcomm23_eval/total_penalty_ratio_75_cdf.dat' u 1:4 with l ls 3 dt "-" title "75%",\

