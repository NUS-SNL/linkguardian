#!/usr/bin/env python
# -*- coding: utf-8 -*-
import numpy as np
import os
import sys
import argparse

def get_cdf(v: list):        
    # calculate cdf
    v_sorted = np.sort(v)
    p = 1. * np.arange(len(v)) / (len(v) - 1)
    od = []
    bkt = [0,0,0,0]
    n_accum = 0
    for i in range(len(v_sorted)):
        key = v_sorted[i]/1000.0 
        n_accum += 1
        if bkt[0] == key:
            bkt[1] += 1
            bkt[2] = n_accum
            bkt[3] = p[i]
        else:
            od.append(bkt)
            bkt = [0,0,0,0]
            bkt[0] = key
            bkt[1] = 1
            bkt[2] = n_accum
            bkt[3] = p[i]
    if od[-1][0] != bkt[0]:
        od.append(bkt)
    od.pop(0)

    ret = ""
    for bkt in od:
        var = str(bkt[0]) + " " + str(bkt[1]) + " " + str(bkt[2]) + " " + str(bkt[3]) + "\n"
        ret += var
        
    return ret



def main():
    parser = argparse.ArgumentParser(description='get CDF of FCTs')
    parser.add_argument('-name', dest='name', action='store', required=True, help="Output filename in /log folder")
    args = parser.parse_args()

    filename = os.getcwd() + "/{}".format(args.name)
    print("Read output log file: {}".format(filename))
    
    if os.path.exists(filename) != True:
        print("ERROR - Cannot find the file!!")
        exit(1)

    fct_arr = []
    with open(filename, "r") as f:
        for line in f.readlines():
            parsed_line = line.replace("\n","").split(",")
            fct_arr.append(float(parsed_line[1]))

    print(get_cdf(fct_arr))

if __name__ == "__main__":
    main()