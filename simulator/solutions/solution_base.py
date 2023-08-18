import enum
import sys
from abc import ABC, abstractclassmethod # abstract base class

sys.path.append("../")
from simulation.link_event import LinkEvent, LinkEventType
from topology.topology import *
from utils.lg_logging import SimulationLogger

class SolutionType(enum.Enum):
    DoNothing = 1
    DisableAndRepair = 2
    CorrOpt = 3
    LinkGuardian = 4
    LG_CorrOpt = 5

class SolutionBase(ABC):
    """ 
    An abstract base class that defines the interface methods to be implemented
    by any derived solution class
    """
    def __init__(self, topo: Topology, sol_params: dict, sol_name: str, logger: SimulationLogger) -> None:
        """ 
        Stores the simulation's Topology object as an attribute for the derived
        solution classes to access easily.
        """
        super().__init__()
        self.topo = topo
        self.sol_params = sol_params
        self.sol_name = sol_name
        self.sim_logger = logger
        # a solution can fill these with key,value pairs 
        # for any summary stats to be printed 
        # at the end of the simulation
        self.sol_summary_stats = {}
    
    @abstractclassmethod
    def process_failure_event(self, event: LinkEvent) -> typing.List[LinkEvent]:
        pass

    @abstractclassmethod
    def post_recovery_event_cb(self, event: LinkEvent) -> typing.List[LinkEvent]:
        pass

    def log(self, msg: str) -> None:
        self.sim_logger.solution_log(self.sol_name, msg)

    def get_summary_stats(self) -> dict:
        return self.sol_summary_stats
