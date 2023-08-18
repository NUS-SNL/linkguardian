#!/usr/bin/env python3
import sys
from simulation.simulation import *

def main():
    if len(sys.argv) != 2:
        print(termcolor.colored("Usage: {} <simulation_config.json>".format(sys.argv[0])))
        sys.exit(1)

    sim_config_file = sys.argv[1]

    # configure the simulation
    sim = Simulation(sim_config_file)
    
    # init the simulation
    sim.init()

    # run the simulation
    # input(termcolor.colored("Press enter to start running the simulation...", "yellow"))
    sim.run()



if __name__ == "__main__":
    main()
