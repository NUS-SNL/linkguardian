#!/usr/bin/env python3

import sys
import re
import tabulate
from termcolor import colored

# checking arguments
if len(sys.argv) != 4:
    print(colored("Usage:",'yellow') + " {} <expt_name> <1/0 blocking or non-blocking> <path to directory>".format(sys.argv[0]))
    sys.exit(1)

expt_name = sys.argv[1]
nb_mode = False

if int(sys.argv[2]) == 1:
    nb_mode = False
elif int(sys.argv[2]) == 0:
    nb_mode = True
else:
    print("Incorrect mode:", sys.argv[2])
    sys.exit(1)

TARGET_DIR = sys.argv[3]


def get_first_and_last_lines(filename):
    with open(filename, 'r') as file:
        first_line = file.readline().strip()
        last_line = None
        for line in file:
            last_line = line.strip()
        return first_line, last_line

############################################
#### Actual and Effective Loss Rates 
############################################
expt_log_file = TARGET_DIR + "/" + expt_name + "_expt.log"

fin_expt_log = open(expt_log_file, 'r')
voa_flr_line = ""
effective_flr_line = ""
for line in fin_expt_log:
    if re.search("VOA FLR", line):
        voa_flr_line = line
    elif re.search("Effective FLR", line):
        effective_flr_line = line
fin_expt_log.close()

voa_flr = float(voa_flr_line.split()[2])
effective_flr = float(effective_flr_line.split()[2])

table = []
table.append(["Actual Loss Rate", str("{:.3e}".format(voa_flr))])
table.append(["Effective Loss Rate", str("{:.3e}".format(effective_flr))])

############################################
#### Effective Link Speed
############################################

forwarded_bytes_file = TARGET_DIR + "/" + expt_name + "_forwarded_byte_counts.dat"

fin_forwarded_bytes = open(forwarded_bytes_file, 'r')

first_line, last_line = get_first_and_last_lines(forwarded_bytes_file)

start_time = float(first_line.split()[0])
end_time = float(last_line.split()[0])
start_bytes = float(first_line.split()[1])
end_bytes = float(last_line.split()[1])

total_bytes = end_bytes - start_bytes
total_time = end_time - start_time

effective_link_speed = total_bytes * (1538/1518) * 8 / total_time

table.append(["Effective Link Speed", str(round(effective_link_speed/1000000000,2)) + " Gbps"])


############################################
#### Buffer Occupancy
############################################

def get_min_max_buff_cells(buff_log_file):
    first_line, last_line = get_first_and_last_lines(buff_log_file)
    max_cells = int(last_line.split()[2])

    fin = open(tx_buff_file, 'r')
    min_cells = pow(2, 32)
    for line in fin:
        cells = int(line.split()[1])
        if cells < min_cells:
            min_cells = cells
    fin.close()

    return min_cells, max_cells

tx_buff_file = TARGET_DIR + "/" + expt_name + "_tx_buff.dat"
min_tx_buff_cells, max_tx_buff_cells = get_min_max_buff_cells(tx_buff_file)

table.append(["TX Buffer Occupancy (min - max)", str(min_tx_buff_cells*80/1000) + " - " + str(max_tx_buff_cells*80/1000) + " KB"])

if nb_mode == False:
    rx_buff_file = TARGET_DIR + "/" + expt_name + "_rx_buff.dat"
    min_rx_buff_cells, max_rx_buff_cells = get_min_max_buff_cells(rx_buff_file)

    table.append(["RX Buffer Occupancy (min - max)", str(min_rx_buff_cells*80/1000) + " - " + str(max_rx_buff_cells*80/1000) + " KB"])

print(tabulate.tabulate(table, headers=["", colored(expt_name + " (non-blocking)" if nb_mode else expt_name + " (blocking)", "yellow")]))
