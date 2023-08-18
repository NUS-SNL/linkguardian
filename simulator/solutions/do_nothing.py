import sys

sys.path.append("../")
from solutions.solution_base import *


class DoNothingSolution(SolutionBase):
    def __init__(self, topo: Topology, sol_params: dict, sim_logger: SimulationLogger) -> None:
        super().__init__(topo, sol_params, "DoNothing", sim_logger)

    # overriding the abstract method
    def process_failure_event(self, event: LinkEvent) -> typing.List[LinkEvent]:
        self.log("Processing the failure event, do-nothing style \m/")
        
        # self.topo provides access to the topology instance
        # BUT, we are going to do nothing here
        # So return a NopeEvent
        return [LinkEvent(-1, LinkEventType.NopEvent, -1, -1)]

    def post_recovery_event_cb(self, event: LinkEvent) -> typing.List[LinkEvent]:
        return [LinkEvent(-1, LinkEventType.NopEvent, -1, -1)]
