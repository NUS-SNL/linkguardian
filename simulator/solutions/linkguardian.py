import sys
import json

sys.path.append("../")
from solutions.solution_base import *
from solutions.corropt import *


class LinkGuardianSolution(SolutionBase):
    def __init__(self, topo: Topology, sol_params: dict, sim_logger: SimulationLogger) -> None:
        super().__init__(topo, sol_params, "LinkGuardian", sim_logger)

        # loading the performance json data
        fin = open(sol_params["lg_performance_json"], 'r')
        perf_json = json.load(fin)
        fin.close()

        # tested loss rate --> (effective loss rate, effective capacity)
        self.loss_rate_to_perf = {}

        for entry in perf_json["perf_data"]:
            self.loss_rate_to_perf[entry["mapped_loss_rate"]] = (entry["effective_loss_rate"], entry["effective_capacity"])

        self.log("Initialized loss rate to effective loss rate and capacity data")

        # tracking corrupting links with linkguardian enabled
        self.curr_active_lg_links = set([])
        

    def get_effective_loss_rate_capacity(self, curr_loss_rate) -> typing.Tuple[float, float]:
        min_distance = sys.maxsize
        closest_tested_loss_rate = None

        for tested_loss_rate in self.loss_rate_to_perf:
            distance = abs(curr_loss_rate - tested_loss_rate)

            if distance < min_distance:
                min_distance = distance
                closest_tested_loss_rate = tested_loss_rate
            
        return self.loss_rate_to_perf[closest_tested_loss_rate]



    # overriding the abstract method
    def process_failure_event(self, event: LinkEvent) -> typing.List[LinkEvent]:
        link_id = event.link_id
        loss_rate = event.loss_rate

        if not self.topo.get_linkguardian_capable(link_id):
            # if link is not LG capable, then can't do anything with vanilla LG
            return [LinkEvent(-1, LinkEventType.NopEvent, -1, -1)]

        effective_loss_rate, effective_capacity = self.get_effective_loss_rate_capacity(loss_rate)

        if self.topo.get_linkguardian_enabled(link_id):
            self.log("Link {} already running LinkGuardian. {} Gbps, {}".format(link_id, self.topo.get_effective_link_capacity(link_id), self.topo.get_link_effective_loss_rate(link_id)))

        #### activate LinkGuardian on the link ####
        # mark the link as LG enabled. Re-enabling doesn't cause any harm
        self.topo.set_linkguardian_enabled(link_id)

        # update effective link capacity
        self.topo.update_effective_link_capacity(link_id, effective_capacity)
        # update effective loss rate
        self.topo.set_link_effective_loss_rate(link_id, effective_loss_rate)

        # track link id as link with LG activated
        self.curr_active_lg_links.add(link_id)

        self.log("(Re)Activated LG on {} [pod {}]: new link capacity: {}, new loss rate: {}".format(link_id, self.topo.link_id_to_pod_id[link_id], effective_capacity, effective_loss_rate))

        return [LinkEvent(-1, LinkEventType.NopEvent, -1, -1)]

    
    # overriding the abstract method
    def post_recovery_event_cb(self, event: LinkEvent) -> typing.List[LinkEvent]:
        # this call back is happening after the link is already enabled
        return [LinkEvent(-1, LinkEventType.NopEvent, -1, -1)]
