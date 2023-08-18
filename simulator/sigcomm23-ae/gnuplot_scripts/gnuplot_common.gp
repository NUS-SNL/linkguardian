# Line style for axes
set style line 80 lt rgb "#000000" # "#808080"

# Line style for grid
set style line 81 lt 0  # dashed
# set style line 81 lt rgb "#808080"  # grey


# Palette 1 from Brighten Godfrey (https://youinfinitesnake.blogspot.com/2011/02/attractive-scientific-plots-with.html)
set style line 1 lt rgb "#A00000" lw 2
set style line 2 lt rgb "#00A000" lw 2
set style line 3 lt rgb "#5060D0" lw 2
set style line 4 lt rgb "#F25900" lw 2

# Palette 2 custom generated from coolors.co
set style line 5 lt rgb "#004ECC" lw 2
set style line 6 lt rgb "#AA2D22" lw 2
set style line 7 lt rgb "#D97F30" lw 2
set style line 8 lt rgb "#962279" lw 2
set style line 9 lt rgb "#E0AC00" lw 2
set style line 10 lt rgb "#0B8381" lw 2
set style line 11 lt rgb "#064279" lw 2
set style line 12 lt rgb "#4939BB" lw 2


set style line 13 lt rgb "#000000" lw 2


set grid back linestyle 81
set border 3 back linestyle 80 # Remove border on top and right.  These
             # borders are useless and make it harder
             # to see plotted lines near the border.
    # Also, put it in grey; no need for so much emphasis on a border.
set xtics nomirror
set ytics nomirror
