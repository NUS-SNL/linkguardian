set terminal pdf size 3,1.8 font ",8"

set output "../../figure15.pdf"

load "../gnuplot_common.gp"

set multiplot layout 3,2 columnsfirst downwards


max_paths_per_tor = 192
max_capacity_per_pod = 19200
start_day = 245.5
end_day = 252.5
xrange_end = end_day - start_day

######  50% - Plot 1  ######

set size 0.58,0.3
set origin 0,0.69

set ylabel "\nTotal Penalty" offset "-1,0"
unset xlabel
set format x ''
set mxtics 4


unset key

set logscale y

set format y "10^{%T}"
set yrange [1e-9: 1e1]
set ytics 1e2

set xrange [0:xrange_end]

plot '../../../output_files/sigcomm23_eval/fbfabric_100k_os1-corropt_50.dat' u (($1/(3600*24))-start_day):3 with l ls 1 title "CorrOpt",\
	'../../../output_files/sigcomm23_eval/fbfabric_100k_os1-lg_corropt_50.dat' u (($1/(3600*24))-start_day):3 with l ls 3 dt "-" title "LinkGuardian + CorrOpt"


######  50% - Plot 2  ######

set size 0.58,0.3
set origin 0,0.41

unset key
unset ylabel
unset yrange
unset format y
unset logscale y

set ytics 10
set mytics 2
set yrange [40:80]

set ylabel "Least Paths\nper ToR (%)"

set label "Capacity Constraint Hit" at 2,65 font ",7"
set arrow from 5,61 to 5.5,53

plot '../../../output_files/sigcomm23_eval/fbfabric_100k_os1-corropt_50.dat' u (($1/(3600*24))-start_day):(($5/max_paths_per_tor)*100) with l ls 1 title "CorrOpt",\
	'../../../output_files/sigcomm23_eval/fbfabric_100k_os1-lg_corropt_50.dat' u (($1/(3600*24))-start_day):(($5/max_paths_per_tor)*100) with l ls 3 dt "-" title "LinkGuardian + CorrOpt"


######  50% - Plot 3  ######

set size 0.58,0.45
set origin 0,0

unset key
unset ylabel
unset yrange

set ylabel "Least Capacity\nper Pod (%)" offset 0,-0.8
set ytics 1
# set yrange [96:99]
set yrange [94:98.2]

set xlabel "Time (days)\nCapacity Constraint: 50\%" offset 0,0.5
unset format x

unset label
unset arrow

plot '../../../output_files/sigcomm23_eval/fbfabric_100k_os1-corropt_50.dat' u (($1/(3600*24))-start_day):(($7/max_capacity_per_pod)*100) with l ls 1 title "CorrOpt",\
	'../../../output_files/sigcomm23_eval/fbfabric_100k_os1-lg_corropt_50.dat' u (($1/(3600*24))-start_day):(($7/max_capacity_per_pod)*100) with l ls 3 dt "-" title "LinkGuardian + CorrOpt"



######  75% - Plot 1  ######

set size 0.5,0.3
set origin 0.53,0.69

# set ylabel "\nTotal Penalty" offset "-1,0"
unset ylabel
set format y ''
unset xlabel
set format x ''
set mxtics 4

# set key top horizontal outside center
unset key

unset mytics

set logscale y
# set format y "10^{%T}"
set yrange [1e-9: 1e1]
set ytics 1e2
set mytics

set xrange [0:xrange_end]

plot '../../../output_files/sigcomm23_eval/fbfabric_100k_os1-corropt_75.dat' u (($1/(3600*24))-start_day):3 with l ls 1 title "CorrOpt",\
	'../../../output_files/sigcomm23_eval/fbfabric_100k_os1-lg_corropt_75.dat' u (($1/(3600*24))-start_day):3 with l ls 3 dt "-" title "LinkGuardian + CorrOpt"


######  75% - Plot 2  ######

set size 0.5,0.3
set origin 0.53,0.41

unset key
unset ylabel
unset yrange
unset format y
unset logscale y

set ytics 10
set mytics 2
set yrange [40:80]

# set ylabel "Least Paths\nper ToR (%)"
unset ylabel
set format y ''

set label "Capacity Constraint Hit" at 2,57 font ",7"
set arrow from 5,61 to 4.5,73


plot '../../../output_files/sigcomm23_eval/fbfabric_100k_os1-corropt_75.dat' u (($1/(3600*24))-start_day):(($5/max_paths_per_tor)*100) with l ls 1 title "CorrOpt",\
	'../../../output_files/sigcomm23_eval/fbfabric_100k_os1-lg_corropt_75.dat' u (($1/(3600*24))-start_day):(($5/max_paths_per_tor)*100) with l ls 3 dt "-" title "LinkGuardian + CorrOpt"


######  75% - Plot 3  ######

set size 0.5,0.45
set origin 0.53,0

unset key
set key vertical at screen 0.8,1 maxrows 1 samplen 2
unset ylabel
unset yrange

# set ylabel "Least Capacity\nper Pod (%)"
unset ylabel
set format y ''

set ytics 1
set yrange [94:98.2]

set xlabel "Time (days)\nCapacity Constraint: 75\%" offset 0,0.5
unset format x

unset label
unset arrow

set label "0.22% reduction" at 0.3,94.75 font ",7"

set arrow from 3.1,95 to 3.2,95.8

plot '../../../output_files/sigcomm23_eval/fbfabric_100k_os1-corropt_75.dat' u (($1/(3600*24))-start_day):(($7/max_capacity_per_pod)*100) with l ls 1 title "CorrOpt",\
	'../../../output_files/sigcomm23_eval/fbfabric_100k_os1-lg_corropt_75.dat' u (($1/(3600*24))-start_day):(($7/max_capacity_per_pod)*100) with l ls 3 dt "-" title "LinkGuardian + CorrOpt"


unset multiplot
