import sys
import os
import heapq
import json
import tabulate
from pathlib import Path
from tqdm import tqdm

sys.path.append("../")
from utils.lg_logging import *
from solutions.do_nothing import *
from solutions.disable_and_repair import *
from solutions.linkguardian_and_corropt import * # also imports vanilla LG and CorrOpt
from topology.topology import *

DATA_DUMPER_START_END_OFFSET = 4 * 24 * 3600  # 4 days


class EventQueue(object):
    def __init__(self) -> None:
        """ 
        Initializes an empty event queue
        """
        self._queue = []
        self.curr_queue_length = 0
        self._timestamp_records = {}

    def is_not_empty(self):
        return len(self._queue) > 0
    
    def add_event(self, event: LinkEvent):
        """ 
        """
        event_time = event.time

        # avoid events with exact same time
        while event_time in self._timestamp_records:
            event_time += 1 # increment time by 1 unit (sec/min)

        # update the time inside the event
        event.time = event_time

        # record the time -> event to avoid time clashes in future
        self._timestamp_records[event_time] = event

        # prepare an entry tuple to add
        entry = (event.time, event)

        heapq.heappush(self._queue, entry)
        
        self.curr_queue_length += 1

    def get_next_event(self) -> LinkEvent:
        """ 
        """
        if self.is_not_empty():
            entry = heapq.heappop(self._queue)
            
            # TODO: delete the event from self._timestamp_records ?
            # del self._timestamp_records[entry[0]] # entry[0] gives the dict key which is time

            return entry[1]  # just the event
        else:
            print(TERM_WARN_STR + "get_next_event() called on an empty event queue. Returning NopeEvent!")
            return LinkEvent(0, LinkEventType.NopEvent, 0, 0)

    def get_head_event_time(self):
        if self.is_not_empty():
            return self._queue[0][0]
        else:
            print(TERM_WARN_STR + "get_head_event_time() called on an empty event queue. Returning 0.")
            return 0


class DataDumper(object):
    def __init__(self, outdir: str, sim_config_file: str) -> None:
        sim_config_file_name = Path(sim_config_file).stem
        self.outfile = outdir + "/" + sim_config_file_name + ".dat"
        self.fout = None
        self.prev_row = None

    def init(self) -> None:
        self.fout = open(self.outfile, "w")
        self.fout.write("time\ttotal_penalty\ttotal_effective_penalty\tavg_per_tor_paths\tmin_per_tor_paths\tavg_per_pod_capacity\tmin_per_pod_capacity\tmax_link_loss_rate\tcurr_disabled_links\tcurr_corrupting_links\tmax_lg_ports_per_pipe\n")

    def dump_row(self, row: tuple) -> None:
        self.fout.write("{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n".format(*row))

    def dump(self, time, total_penalty, total_effective_penalty, avg_per_tor_paths, min_per_tor_paths, avg_per_pod_capacity, min_per_pod_capacity, max_loss_rate, curr_disabled_links, curr_corrupting_links, max_lg_ports_per_pipe) -> None:
        curr_row = (time, total_penalty, total_effective_penalty, avg_per_tor_paths, min_per_tor_paths, avg_per_pod_capacity, min_per_pod_capacity, max_loss_rate, curr_disabled_links, curr_corrupting_links, max_lg_ports_per_pipe)
        
        if self.prev_row == None: # this is the first data row
            self.prev_row = curr_row
            self.dump_row(curr_row)
        else:
            assert self.prev_row[0] != curr_row[0], "curr row has the same timestamp as previous row"

            # for plotting of line graph
            # repeat previous data but with new timestamp
            # because until this point the system had the
            # data from the prev row
            curr_time = curr_row[0]
            prev_row_with_curr_time = (curr_time, self.prev_row[1], self.prev_row[2], self.prev_row[3], self.prev_row[4], self.prev_row[5], self.prev_row[6], self.prev_row[7], self.prev_row[8], self.prev_row[9], self.prev_row[10])
            self.dump_row(prev_row_with_curr_time)
            self.dump_row(curr_row)
            self.prev_row = curr_row

    def dump_last_row(self) -> None:
        """ 
        This is to repeat the last metrics values at somewhat later time,
        since no network state change has occurred till then!
        Only helps to make the graph look "pretty" with originally dumped data. 
        """
        prev_time = self.prev_row[0]
        last_row = (prev_time + DATA_DUMPER_START_END_OFFSET, self.prev_row[1], self.prev_row[2], self.prev_row[3], self.prev_row[4], self.prev_row[5], self.prev_row[6], self.prev_row[7], self.prev_row[8], self.prev_row[9], self.prev_row[10])
        self.dump_row(last_row)

    # destructor
    def __del__(self) -> None:
        if self.fout != None:
            self.fout.close()


class Simulation(object):
    def __init__(self, config_file) -> None:
        # parse the config_file JSON and init attributes
        with open(config_file, 'r') as fin:
            config_file_json = json.load(fin)
        
        # topology-related
        topo_json = config_file_json["topology"]
        self.topo_type = TopoType(topo_json["topo_type"])
        self.topo_params = topo_json["topo_params"]

        # failure trace
        failure_trace_file = config_file_json["failure_event_trace"]
        with open(failure_trace_file, 'r') as fin:
            self.failure_trace_json = json.load(fin)
        failure_trace_topo_type = TopoType(self.failure_trace_json["topo_type"])
        failure_trace_topo_params = self.failure_trace_json["topo_params"]

        # solution
        self.solution_type = SolutionType(config_file_json["solution"])
        self.solution_params = config_file_json["solution_params"]
        self.solution = None

        # output_dir
        self.output_dir = config_file_json["output_dir"]
        # check if the output dir exists. If not, create one. 
        if not os.path.exists(self.output_dir):
            print(TERM_WARN_STR + "Output directory '{}' does not exist".format(self.output_dir))
            print("Creating the same ...")
            try:
                os.makedirs(self.output_dir, mode=0o775, exist_ok=True)
            except Exception as e:
                print("\n" + TERM_ERROR_STR +  str(e))
                sys.exit(1)

        # init the logger
        self.sim_logger = SimulationLogger(self.output_dir, config_file)

        # logging method aliases
        self.log = self.sim_logger.simulation_log
        self.log_recovery_event = self.sim_logger.simulation_log_recovery_event

        # attributes specific to the simulation
        self.is_initialized = False
        self.event_queue = EventQueue()

        # instantiate the data_dumper
        self.data_dumper = DataDumper(self.output_dir, config_file)

        # init the skipped loss event count
        self.skipped_loss_events = 0

        # init the added recovery event counter
        self.added_recovery_events = 0

        # Checking if the topo matches the failure trace
        if self.topo_type != failure_trace_topo_type:
            print(TERM_ERROR_STR + "The topo_types for simulation and failure trace are different: {} {} and respectively".format(self.topo_type.name, failure_trace_topo_type.name))
            sys.exit(1)
        else: # the topo_type matches, now check the topo_params
           for param in self.topo_params:
                if self.topo_params[param] != failure_trace_topo_params[param]:
                    print(TERM_ERROR_STR + "The topo param '{}' does not match. Topo has value {}, failure trace has value {}.".format(param, self.topo_params[param], failure_trace_topo_params[param]))
                    sys.exit(1)

        print(termcolor.colored("Simulation config is correct!", "green"))
        self.log("Simulation config is correct!", False, True)

        table = []
        table.append(["topo_type:", "{}".format(self.topo_type.name)])
        table.append(["topo_params:", "{}".format(self.topo_params)])
        table.append(["failure_trace_file:", "{}".format(failure_trace_file)])
        table.append(["solution:", "{}".format(self.solution_type.name)])
        table.append(["solution_params:", "{}".format(self.solution_params)])
        self.log("\n" + tabulate.tabulate(table), False, True)


    def init(self) -> None: 
        # build the topo
        # print("Building {} topo with params {} ... ".format(self.topo_type.name, self.topo_params), end="", flush=True)
        self.topo = Topology(self.topo_type, self.sim_logger)

        # Passing partial deployment param from sol_params to topo_params
        if 'deployment_percent' in self.solution_params:
            self.topo_params['deployment_percent'] = self.solution_params['deployment_percent']
        else: # otherwise by default the deployment is 100%
            self.topo_params['deployment_percent'] = 100

        spinner = Spinner("Building {} topo with params {} ... ".format(self.topo_type.name, self.topo_params), end="", flush=True)
        self.topo.build(self.topo_params, spinner)
        spinner.finish()
        print(TERM_DONE_STR)
        self.log("Done building {} topo with params {}".format(self.topo_type.name, self.topo_params), False, False)
        if self.solution_type == SolutionType.LG_CorrOpt or self.solution_type == SolutionType.LinkGuardian:
            lg_enabled_links =  self.topo.num_lg_enabled_links
            total_links = self.topo.num_links
            percent_lg_links = round(lg_enabled_links / total_links * 100, 2)
            self.log("Fraction of links LG-enabled: {}/{} = {}%".format(lg_enabled_links, total_links, percent_lg_links), False, True)

        # load the failure trace into the event queue
        print("Loading the failure trace into the event queue... ", end="", flush=True)
        for failure_event in self.failure_trace_json["failure_events_list"]:
            time = failure_event[0]
            link_id = failure_event[1]
            loss_rate = failure_event[2]
            event = LinkEvent(time, LinkEventType.FailureEvent, link_id, loss_rate)
            self.event_queue.add_event(event)
        print(TERM_DONE_STR)
        self.log("Done loading the failure trace into the event queue", False, False)

        self.input_failure_events = self.event_queue.curr_queue_length

        # initialize the solution class
        if self.solution_type == SolutionType.DoNothing:
            self.solution = DoNothingSolution(self.topo, self.solution_params, self.sim_logger)
        elif self.solution_type == SolutionType.DisableAndRepair:
            self.solution = DisableAndRepairSolution(self.topo, self.solution_params, self.sim_logger)
        elif self.solution_type == SolutionType.CorrOpt:
            self.solution = CorrOptSolution(self.topo, self.solution_params, self.sim_logger)
        elif self.solution_type == SolutionType.LinkGuardian:
            self.solution = LinkGuardianSolution(self.topo, self.solution_params, self.sim_logger)
        elif self.solution_type == SolutionType.LG_CorrOpt:
            self.solution = LGCorrOptSolution(self.topo, self.solution_params, self.sim_logger)

    def process_event(self, event: LinkEvent) -> bool:
        """
        Handles the processing of the link event

        Returns True if event is processed. False, if skipped. 
        """
        is_link_disabled = self.topo.is_link_disabled(event.link_id)

        if event.type == LinkEventType.FailureEvent:
            self.log("Link {} [{}] failure at {} with loss rate {:e}".format(event.link_id, self.topo.get_link_type(event.link_id), event.time, event.loss_rate))

            if is_link_disabled:
                # link is already disabled
                # trace has another failure event on the link
                # even before the link is recovered
                # CAN'T HELP IT: traceGen doesn't know what solution would be
                # used and whether it will disable any link or not
                # link could just be showing varying corruption rate

                # update the count and return
                self.skipped_loss_events += 1
                self.log("Skipping event since link is already disabled!")
                return False # the event was skipped
    
            # record the loss rate into top loss rates heap
            # IMP Note: this MUST be done *before* setting (new) 
            # loss rate on the link helps handle cases when existing corrupting
            # link changes corruption rate
            self.topo.record_link_top_loss_rates(event.link_id, event.loss_rate)

            # set loss rate on the link
            self.topo.set_link_loss_rate(event.link_id, event.loss_rate)

            # add the link to the list of corrupting links
            self.topo.corrupting_links.add(event.link_id)

            # set effective loss rate on the link
            # in case of LinkGuardian already enabled on the link, 
            # the effective loss rate is not affected by the failure trace
            # so only set effective loss rate if LG is not already enabled
            if not self.topo.get_linkguardian_enabled(event.link_id):
                self.topo.set_link_effective_loss_rate(event.link_id, event.loss_rate)
            
            # call the solution's failure event handler
            sol_requested_events = self.solution.process_failure_event(event)

            for sol_requested_event in sol_requested_events:
                assert sol_requested_event.type != LinkEventType.FailureEvent, \
                "A solution cannot request a failure event"
        
                if sol_requested_event.type == LinkEventType.RecoveryEvent:
                    # solution wants us to schedule a recovery event
                    self.event_queue.add_event(sol_requested_event)
                    self.added_recovery_events += 1
            
        elif event.type == LinkEventType.RecoveryEvent:
            # enable the link first
            self.topo.enable_link(event.link_id) # also, sets the initial loss rate
            # print(termcolor.colored("[Recovered] ", "green") + "Link id
            # {}".format(event.link_id))
            self.log_recovery_event(event, self.topo.get_link_type(event.link_id))
            # then call the solution's recovery cb
            sol_requested_events = self.solution.post_recovery_event_cb(event)
            self.log("Num events requested by sol recovery cb: {}".format(len(sol_requested_events)))
            for sol_requested_event in sol_requested_events:
                assert sol_requested_event.type != LinkEventType.FailureEvent, \
                    "A solution cannot request a failure event"

                if sol_requested_event.type == LinkEventType.RecoveryEvent:
                    # the solution has disabled some link(s) and 
                    # wants us to schedule a recovery event(s)
                    self.event_queue.add_event(sol_requested_event)
                    self.log("solution cb scheduled recovery: link {} at {}".format(sol_requested_event.link_id, sol_requested_event.time))
                    self.added_recovery_events += 1

        return True # the event was processed

    
    def get_current_metrics(self) -> tuple:
        total_penalty = self.topo.total_loss_rate
        total_effective_penalty = self.topo.total_effective_loss_rate
        avg_per_tor_paths = self.topo.get_avg_num_paths_to_core()
        min_per_tor_paths = self.topo.get_min_num_paths_to_core()
        avg_per_pod_capacity = self.topo.get_avg_per_pod_capacity_to_core()
        min_per_pod_capacity = self.topo.get_min_per_pod_capacity_to_core()
        max_link_loss_rate = self.topo.get_max_link_loss_rate()
        curr_disabled_links = len(self.topo.disabled_links)
        curr_corrupting_links = len(self.topo.corrupting_links)
        max_lg_ports_per_pipe = self.topo.get_max_lg_ports_per_pipe()

        return (total_penalty, total_effective_penalty, avg_per_tor_paths, min_per_tor_paths, avg_per_pod_capacity, min_per_pod_capacity, max_link_loss_rate, curr_disabled_links, curr_corrupting_links, max_lg_ports_per_pipe)


    def run(self) -> None:
        """ 
        Runs the event_queue's processing
        """
        # initialize the data_dumper
        self.data_dumper.init() # opens the outfile

        self.log("-------------------------------------------")
        self.log("Initial Total Penalty: {}".format(self.topo.total_loss_rate))
        self.log("Initial Total Effective Penalty: {}".format(self.topo.total_loss_rate))

        event_counter = 1
        processed_event_counter = 0

        # dump initial state
        current_metrics = self.get_current_metrics()
        initial_time = self.event_queue.get_head_event_time() - DATA_DUMPER_START_END_OFFSET # subtract 4 days
        self.data_dumper.dump(initial_time, *current_metrics)

        self.log("Initial min per pod capacity: {}".format(current_metrics[-4]))

        print("Simulation running...")
        progress_bar = tqdm(total=self.event_queue.curr_queue_length, unit='events')
        while self.event_queue.is_not_empty():
            event = self.event_queue.get_next_event()
            self.log("---------- Processing: {} ({}/{}) ----------".format(event.type.name, event_counter, self.event_queue.curr_queue_length), True)
            if self.process_event(event):
                processed_event_counter += 1 # increase counter only if event is processed
            event_counter += 1
            progress_bar.update(1)
            progress_bar.total = self.event_queue.curr_queue_length
            # print("Total penalty after event processing: {}".format(self.topo.total_loss_rate))

            # dump the current metrics
            # TODO: get and dump metrics only if the event is processed
            #       i.e. event was not skipped due to link already disabled
            current_metrics = self.get_current_metrics()
            self.data_dumper.dump(event.time, *current_metrics)
            self.log("Min per pod capacity: {}".format(current_metrics[-4]))
            # self.log("Per pod capacities:")
            # for pod in self.topo.per_pod_capacity:
            #     self.log("{}: {}".format(pod, self.topo.per_pod_capacity[pod]))
            self.log("Effective loss rate: {}".format(current_metrics[1]))
            self.log("Loss rate: {}".format(current_metrics[0]))
        
        progress_bar.close()

        self.log("-------------------------------------------")
        self.log("Final Total Penalty: {}".format(self.topo.total_loss_rate), True)
        self.log("Final effective total penalty: {}".format(self.topo.total_effective_loss_rate))
        self.log("Final min per pod capacity: {}".format(current_metrics[-4]))
        
        self.data_dumper.dump_last_row()

        #--------------   Generate Simulation Summary   --------------
        table = []
        table.append(["Input loss events from the trace:","{}".format(self.input_failure_events)])
        table.append(["Skipped loss events due to link disabled:", "{}".format(self.skipped_loss_events)])
        table.append(["Added recovery events:","{}".format(self.added_recovery_events)])
        table.append(["Total events processed:", "{} ({} - {} + {})".format(processed_event_counter, self.input_failure_events, self.skipped_loss_events, self.added_recovery_events)])

        # get solution summary stats
        sol_summary_stats = self.solution.get_summary_stats()
        if len(sol_summary_stats) != 0:
            # add a separator
            table.append(["-----------------------------------------", "---------------------"])
            table.append(["{}:".format(self.solution.sol_name), ""])
            for key in sol_summary_stats:
                table.append([key, "{}".format(sol_summary_stats[key])])

        print(termcolor.colored("\nSimulation Summary:", "yellow"))
        self.log("Simulation Summary")
        print(tabulate.tabulate(table))
        self.log(tabulate.tabulate(table))

        print(termcolor.colored("Output file(s):", "yellow"))
        print(self.data_dumper.outfile)
        print(self.sim_logger.logfile)
        
