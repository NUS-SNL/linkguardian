#!/usr/bin/env python3

import sys
import os
import termcolor
import json
import csv
import typing
import numpy as np
import pandas as pd
from tqdm import tqdm

sys.path.append("../")
from utils.lg_logging import *
from topology.topology import TopoType
from loss_rate_generator import LossRateGenerator
from simulation.simulation import DATA_DUMPER_START_END_OFFSET, EventQueue, LinkEvent
from simulation.link_event import LinkEventType


WEIBULL_PARAM_SHAPE = 1 # since in our case random external events cause failure

NUM_LOSS_EVENTS_PER_LINK = 10  # gives sufficiently longer trace

required_json_fields = ["name", 
    "topo_type", "topo_params", 
    # "total_failure_events", 
    "loss_rate_dist_file",
    # "inter_arrival_dist_file",
    "mttf_hrs",
    "max_duration_hrs"]

def is_valid_input_json(json_dict):
    for field in required_json_fields:
        if field not in json_dict:
            return False
    return True

generated_outfiles = []

def generate_failure_events_weibull(max_trace_duration_hrs: int, num_links: int, loss_rate_generator: LossRateGenerator, mttf_hrs: int) -> typing.List[typing.Tuple[int, int, float]]:
    """ 
    Generates the loss events and returns them as an EventQueue

    Arguments:
        max_trace_duration: int. Total number of hrs of trace to generate
        num_links: int. Total number of links in the topology
        loss_rate_generator: an instance of LossRateGenerator
        mttf_hrs: int. The MTTF parameter for the Weibull distribution.

    Returns:
        list of loss events. Loss event is a tuple: (event_time, link_id, loss_rate) 
    """
    # Step 1: instantiate per-link random generators
    print("Initializing per-link random generators... ", flush=True, end="")
    per_link_rngs = {}

    for i in range(num_links):
        per_link_rngs[i] = np.random.default_rng()
    
    print(TERM_DONE_STR, flush=True)

    # Step 2: generate failure times per link
    print("Generating {} failure times per link... ".format(NUM_LOSS_EVENTS_PER_LINK), flush=True, end="")

    per_link_failure_times = {}

    for link in per_link_rngs:
        rng = per_link_rngs[link]
        failure_times = []
        
        # get one initial time to fail
        time_to_fail = round(mttf_hrs * rng.weibull(WEIBULL_PARAM_SHAPE))
        
        failure_times.append(time_to_fail)

        for i in range(NUM_LOSS_EVENTS_PER_LINK - 1):
            prev_failure_time = failure_times[-1]
            time_to_fail = round(mttf_hrs * rng.weibull(WEIBULL_PARAM_SHAPE))
            new_failure_time = prev_failure_time + time_to_fail
            failure_times.append(new_failure_time)
            
        per_link_failure_times[link] = failure_times

    print(TERM_DONE_STR, flush=True)

    # Step 3: generate a LinkEvent for all failures of all links
    #         and add it to the EventQueue
    print("Generating all failure events into an EventQueue...")
    event_queue = EventQueue()
    for link in tqdm(range(num_links)):
        for failure_time in per_link_failure_times[link]:
            # get the loss rate from the loss rate distribution
            loss_rate = loss_rate_generator.generate()
            loss_event = LinkEvent(failure_time * 3600, LinkEventType.FailureEvent, link, loss_rate)
            event_queue.add_event(loss_event)


    # Step 4: Generate a loss event list from the loss event queue
    print("Generating loss event list of max duration {} hrs... ".format(max_trace_duration_hrs), flush=True, end="")
    loss_event_list = []
    head_event_time = event_queue.get_head_event_time()
    expected_last_event_time = head_event_time + (max_trace_duration_hrs * 3600)
    
    while head_event_time <= expected_last_event_time:
        curr_event = event_queue.get_next_event()
        loss_event_list.append((curr_event.time + DATA_DUMPER_START_END_OFFSET, curr_event.link_id, curr_event.loss_rate))
        head_event_time = event_queue.get_head_event_time()

    print(TERM_DONE_STR, flush=True)

    return loss_event_list


def generate_interarrival_times(event_list: list, trace_name: str, output_dir: str) -> None:
    """ 
    Generates 2 files: interarrival_times, interarrival_times_summary

    Arguments:
        event_list: list of (event_time, link_id, loss_rate)
        trace_name: str. Name of the trace to be generated.
    """

    outfile = output_dir +  "/" + trace_name + "-interarrival_times.dat"
    outfile_summary = output_dir +  "/" + trace_name + "-interarrival_times-summary.dat"

    failure_interarrival_times = []

    prev = event_list[0][0]

    for failure_event in event_list[1:]:
        curr = failure_event[0]
        interarrival = curr - prev
        failure_interarrival_times.append(interarrival)
        prev = curr

    print("Writing interarrival times to file... ",end="", flush=True)
    fout = open(outfile, "w")
    for interarrival in failure_interarrival_times:
        fout.write("{}\n".format(interarrival))
    fout.close()
    print(TERM_DONE_STR)

    df = pd.DataFrame(np.array(failure_interarrival_times), columns=['interarrival'])

    df_summary = df.describe(percentiles=[.5, .75, .9, .95, .99, .999, .9999,.99999], include='all')
    df_summary = df_summary.round(3)
    df_summary = df_summary.reindex(["min","mean","50%","75%","90%","95%","99%","99.9%","99.99%","99.999%","max","std","count"])

    print("Writing interarrival times summary to file... ",end="", flush=True)
    df_summary.to_csv(outfile_summary, sep="\t", quoting=csv.QUOTE_NONE)
    print(TERM_DONE_STR)

    generated_outfiles.append(outfile)
    generated_outfiles.append(outfile_summary)
   

def main():
    if len(sys.argv) != 2:
        print(TERM_ERROR_STR + "Invalid arguments")
        print(termcolor.colored("Usage: ", "yellow") + "{} <loss_trace_config.json>".format(sys.argv[0]))
        sys.exit(1)

    config_file = sys.argv[1]

    # load the json file in a dict
    fin_json = open(config_file, 'r')
    json_dict = json.load(fin_json)
    fin_json.close()

    # check if input files has the required fields
    if(not is_valid_input_json(json_dict)):
        print(TERM_ERROR_STR + "Invalid input file")
        print("Required JSON input fields:")
        for field in required_json_fields:
            print(field)
        sys.exit(1)

    # extract the input fields
    trace_name = json_dict["name"]
    topo_type = TopoType(json_dict["topo_type"])
    topo_params = json_dict["topo_params"]
    # total_failure_events =  json_dict["total_failure_events"]
    loss_rate_dist_file = json_dict["loss_rate_dist_file"]
    # interarrival_dist_file = json_dict["inter_arrival_dist_file"]
    max_duration_hrs = json_dict["max_duration_hrs"]
    mttf_hrs = json_dict["mttf_hrs"]
    output_dir = json_dict["output_dir"]

    #  compute num_links based on the input topology
    if topo_type == TopoType.FatTree:
        k = topo_params['k']
        num_links = pow(k, 3) / 2
    elif topo_type == TopoType.LeafSpine:
        print(TERM_WARN_STR + "Loss trace generator doesn't YET know num_links for a LeafSpine topo")
        sys.exit(0)
    elif topo_type == TopoType.FbFabric:
        oversubscription = topo_params['oversubscription']
        tors_per_pod = topo_params['tors_per_pod']
        core_switches_per_spine_plane = tors_per_pod / oversubscription
        num_links_per_pod = (4 * tors_per_pod) + (4 * core_switches_per_spine_plane)
        num_pods = topo_params['num_pods']
        num_links = num_pods * num_links_per_pod

    print(TERM_INFO_STR + "Generating loss trace for total links = {}".format(int(num_links)))

    # Initialize the loss rate generator
    loss_rate_generator = LossRateGenerator(loss_rate_dist_file)

    # The MAIN function that generates the failure events
    loss_event_list = generate_failure_events_weibull(max_duration_hrs, int(num_links), loss_rate_generator, mttf_hrs)

    first_event_time = loss_event_list[0][0]
    last_event_time = loss_event_list[-1][0]

    # Check for output directory and create if it doesn't exist
    if not os.path.exists(output_dir):
        print(TERM_WARN_STR + "Output directory '{}' does not exist".format(output_dir))
        print("Creating the same ...")
        try:
            os.makedirs(output_dir, mode=0o775, exist_ok=True)
        except Exception as e:
            print("\n" + TERM_ERROR_STR +  str(e))
            sys.exit(1)

    # for analysis/testing purposes. Compute and dump interarrival times
    # generate_interarrival_times(loss_event_list, trace_name, output_dir)

    # Dump the trace to the final JSON output format
    trace_output_dict = {}

    trace_output_dict["name"] = trace_name
    trace_output_dict["topo_type"] = topo_type.value
    trace_output_dict["topo_params"] = topo_params
    trace_output_dict["num_links"] = num_links
    trace_output_dict["total_failure_events"] = len(loss_event_list) # total_failure_events
    trace_output_dict["first_event_time"] = first_event_time
    trace_output_dict["last_event_time"] = last_event_time
    trace_output_dict["trace_duration_hrs"] = last_event_time - first_event_time
    trace_output_dict["failure_events_list"] = [list(event) for event in loss_event_list]

    outfile = output_dir + "/" + trace_name + "-trace.json"
    print("Writing the entire trace to the output file... ", end="", flush=True)
    with open(outfile, 'w') as fout:
        json.dump(trace_output_dict, fout, indent=4)
    print(TERM_DONE_STR)

    generated_outfiles.append(outfile)

    print(termcolor.colored("The following files were generated:", "yellow"))
    print("{}".format("\n".join(generated_outfiles)))


if __name__ == "__main__":
    main()
