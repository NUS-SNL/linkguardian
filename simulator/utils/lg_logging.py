import sys
import termcolor
from pathlib import Path

sys.path.append("../")
from simulation.link_event import LinkEvent
from topology.topo_types import LinkType

TERM_ERROR_STR = termcolor.colored("ERROR: ", "red")
TERM_WARN_STR = termcolor.colored("WARN: ", "yellow")
TERM_INFO_STR = termcolor.colored("INFO: ", "yellow")
TERM_DONE_STR = termcolor.colored("Done", "green")


class SimulationLogger(object):
    def __init__(self, outdir, config_file) -> None:
        # TODO: include proper file + console logging
        # Param-based disabling of either or both logging
        sim_config_file_name = Path(config_file).stem
        self.logfile = outdir + "/" + sim_config_file_name + ".log"
        self.fout = open(self.logfile, 'w')
    
    def simulation_log(self, msg: str, newline_before: bool = False, console_log: bool = False) -> None:
        if newline_before:
            before_new_line = "\n"
        else:
            before_new_line = ""
        if console_log:
            print(before_new_line + termcolor.colored("[Sim] ", "yellow") + msg)
        self.fout.write(before_new_line + "[Sim] " + msg + "\n")

    def simulation_log_recovery_event(self, event: LinkEvent, link_type: LinkType, console_log: bool = False) -> None:
        if console_log:
            self.simulation_log(termcolor.colored("Recovered: ", "green") + "Link id {} [{}] at {}".format(event.link_id, link_type.name, event.time), False, console_log)
        else:
            self.simulation_log("Recovered: " + "Link {} [{}] at {}".format(event.link_id, link_type.name, event.time), False, console_log)
    
    def solution_log(self, sol_name: str, msg: str, console_log: bool = False) -> None:
        if console_log:
            print(termcolor.colored("[{}] ".format(sol_name), "cyan") + msg)
        self.fout.write("[{}] ".format(sol_name) + msg + "\n")

    def __del__(self) -> None:
        if self.fout != None:
            self.fout.close()
