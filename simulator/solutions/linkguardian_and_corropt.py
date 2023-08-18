import sys
import json

sys.path.append("../")
from solutions.solution_base import *
from solutions.corropt import *
from solutions.linkguardian import *


class LGCorrOptSolution(SolutionBase):
    def __init__(self, topo: Topology, sol_params: dict, sim_logger: SimulationLogger) -> None:
        super().__init__(topo, sol_params, "LG_CorrOpt", sim_logger)

        # initialize an instance of pure LinkGuardian
        self.linkguardian = LinkGuardianSolution(topo, sol_params, sim_logger)

        # initialize an instance of pure CorrOpt
        self.corropt = CorrOptSolution(topo, sol_params, sim_logger)

        # solution stats initialization
        self.sol_summary_stats["Fast checker: failed to disable"] = 0
        self.sol_summary_stats["Failed Link Events on links w/o LG"] = 0
        self.sol_summary_stats["Loss events both LG and CorrOpt failed to handle"] = 0

        # TODO: activate the following block when using fall back CorrOpt?
        """ 
        # convert capacity constraint into min_active_paths
        # Step 1: get the initial active paths for any 1 ToR (symmetric topos,
        # of course!)
        capacity_constraint_percent = sol_params["capacity_constraint_percent"]
        any_tor_id = self.topo.switch_typewise_list[SwitchType.TOR][0]
        initial_paths_to_core = self.topo.get_num_paths_to_core(any_tor_id)

        # Step 2: compute the capacity constraint
        self.min_active_paths_constraint = math.ceil(initial_paths_to_core * capacity_constraint_percent / 100)

        self.log("Initialized with per-tor min active paths constraint of {} (for fallback CorrOpt)".format(self.min_active_paths_constraint))
        """

    # overriding the abstract method
    def process_failure_event(self, event: LinkEvent) -> typing.List[LinkEvent]:
        link_id = event.link_id
        loss_rate = event.loss_rate

        if not self.topo.get_linkguardian_capable(link_id):
            # if link is not LG capable, then we fall back to CorrOpt's
            # fast_checker
            self.log("Link {} [pod {}] is not LG-capable. Falling back to CorrOpt's fast checker".format(link_id, self.topo.link_id_to_pod_id[link_id]))
            self.sol_summary_stats["Failed Link Events on links w/o LG"] += 1
            fc_new_event_list = [self.corropt.corropt_fast_checker(event)]
        else:
            # Here onward, the link is LG-capable

            # Step 1: activate LG on the link i.e. call LG's process_failure_event
            # this one always returns a nop_event
            nop_event = self.linkguardian.process_failure_event(event)

            # Step 2: run CorrOpt's fast checker to figure out if the link can be
            # disabled.         
            fc_new_event_list = [self.corropt.corropt_fast_checker(event)]

        if fc_new_event_list[0].type == LinkEventType.NopEvent:
            self.sol_summary_stats["Fast checker: failed to disable"] += 1
            if not self.topo.get_linkguardian_capable(link_id): # NOT LG-capable link
                self.sol_summary_stats["Loss events both LG and CorrOpt failed to handle"] += 1

        return fc_new_event_list

    
    # overriding the abstract method
    def post_recovery_event_cb(self, event: LinkEvent) -> typing.List[LinkEvent]:
        # this call back is happening after the link is already enabled
        
        # just call the CorrOpt's optimizer 
        requested_events = self.corropt.corropt_optimizer(event)

        # TODO?: MC suggested optimizer variation which optimizes to disable
        # links which are most capacity reducing. I don't think if that would
        # result in anything different
        return requested_events

