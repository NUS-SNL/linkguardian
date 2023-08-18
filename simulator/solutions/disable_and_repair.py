import sys

sys.path.append("../")
from solutions.solution_base import *


class DisableAndRepairSolution(SolutionBase):
    def __init__(self, topo: Topology, sol_params: dict, sim_logger: SimulationLogger) -> None:
        super().__init__(topo, sol_params, "Disable-Repair", sim_logger)

    # overriding the abstract method
    def process_failure_event(self, event: LinkEvent) -> typing.List[LinkEvent]:
        self.log("Processing the failure event, disable-and-repair style \m/")
        
        link_id = event.link_id

        # disable the link
        self.topo.disable_link(link_id)

        # Prepare a recovery event 4 days later
        recovery_time = event.time + (4 * 24 * 3600)  # 4 days (in seconds)
        return [LinkEvent(recovery_time, LinkEventType.RecoveryEvent, link_id, 0)]

    def post_recovery_event_cb(self, event: LinkEvent) -> typing.List[LinkEvent]:
        return [LinkEvent(-1, LinkEventType.NopEvent, -1, -1)]
