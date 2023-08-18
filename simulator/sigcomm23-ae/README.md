# LinkGuardian SIGCOMM'23 AE (simulator)
## Overview

The simulator artifact of LinkGuardian consists of two sub-artifacts:
1. The main topology-level simulator (sections 3.6 and 4.8)
2. The trace generator (Appendix D)

**Goal:** To show that the simulator artifacts are functional, we will first run
the simulations for 50% capacity constraint using the same link corruption trace
that was used in the paper. Then we will process the simulation output files and
plot Figures 15 and 16 with data corresponding to 50% capacity constraint. We
will also run the trace generator and check if it is functional.

This README will guide you through the evaluation process which consists of the following steps:
1. [Setting up the system with dependencies](#system-setup) (5-7 mins)
2. [Building the Docker container](#building-the-container) (5-10 mins,
   depending on your Internet connection speed.)
3. [Running simulations for 50% capacity constraint](#simulations-for-50-constraint) (15-20 mins, depending on
   your CPU's single-core performance)
4. [Processing data and plotting graphs](#processing-results-for-50-capacity-constraint) (< 2 mins)
5. \[Optional\] [Running simulations and plotting graphs for 75% capacity
   constraint](#simulations-for-75-capacity-constraint) for *full reproducibility* (~7-8
   hours)
6. [Running the trace generator](#trace-generator) (3-5 mins)

### System Requirements
We recommend using a VM or a bare metal machine with the following specifications:
* Ubuntu 18.04 or above
* 4+ CPU cores
* 15+ GB of free disk space
* 8+ GB of RAM


## Artifact Evaluation Process 
> **Note**
> The following steps assume that you have cloned the main Github repository and
> are currently inside the `simulator/sigcomm23-ae` (this!) directory which
> contains a handy `Makefile`.

### System Setup

Since, we have Dockerized the simulator artifact, our dependencies are only the
GNU Make and the Docker Engine.

Install GNU Make:
```
sudo apt install build-essential
```
Install Docker Engine:

For Ubuntu, following the installation guide
[here](https://docs.docker.com/engine/install/ubuntu/) and make sure to apply
the necessary post-install
[steps](https://docs.docker.com/engine/install/linux-postinstall/).Eventually,
you should be able to launch the `hello-world` Docker container without `sudo`
command: 
```
docker run hello-world
```

### Building the Container

Build the Docker container which contains the necessary dependencies to run the simulations and reproduce the plots.

```
make build_container
```

The resulting container image, `lg-sim:sigcomm23ae`, should take up approximately 1.3 GB of disk space.
Verify that the container is successfully built using the command:
```
docker image ls
```
The following output is expected:

```
user@server:~/linkguardian-simulator/sigcomm23-ae$ docker image ls
REPOSITORY    TAG                  IMAGE ID       CREATED         SIZE
...
lg-sim        sigcomm23ae          3eb7b0f7e302   4 minutes ago    1.29GB
...
```

### Simulations for 50% capacity constraint

Figures 15 and 16 in the paper show the results for CorrOpt and LinkGuardian +
CorrOpt with 50% and 75% capacity constraints each. The expected runtimes for
each simulation are as follows: 
|     | **CorrOpt** | **LinkGuardian+CorrOpt** |
|:---:|:-----------:|:------------------------:|
| 50% |   ~10 min.  |         ~10 min.         |
| 75% |   ~7-8 hrs.  |        ~7-8 hrs.         |

In the interest of the evaluator's time, here we run the simulations for only
the 50% capacity constraint. We believe that this is sufficient to show that the
simulator artifact is *functional*.

Run the simulations for 50% capacity constraint:
```
make simulate_50
```

This will first run the simulation for CorrOpt followed by LinkGuardian +
CorrOpt. The expected duration is 15-20 mins. Feel free to go and grab a coffee :) 

#### Expected Output 
When running the simulations you should expect the following output:
```
...
Building FbFabric topo with params ... 
Done
...
Loading the failure trace into the event queue... Done
Simulation running...
  6%|█████▌                                                                                              | 5220/92991 [00:08<02:37, 557.66events/s]
```

Upon completion, you should expect the following *complete* output:
```
...
Building FbFabric topo with params ... 
Done
...
Loading the failure trace into the event queue... Done
Simulation running...
100%|███████████████████████████████████████████████████████████████████████████████████████████████████| 179693/179693 [04:55<00:00, 607.48events/s]

Simulation Summary:
-----------------------------------------  ----------------------------
Input loss events from the trace:          90109
Skipped loss events due to link disabled:  525
Added recovery events:                     89584
Total events processed:                    179168 (90109 - 525 + 89584)
-----------------------------------------  ---------------------
CorrOpt:
Fast checker: failed to disable            453
-----------------------------------------  ----------------------------
Output file(s):
./output_files/sigcomm23_eval/fbfabric_100k_os1-corropt_50.dat
./output_files/sigcomm23_eval/fbfabric_100k_os1-corropt_50.log
```

For each simulation run, the simulator generates a data and a log file. The four
output files (due to 2 simulation runs) can be found in the `output_files`
folder at the simulator root directory. 

Check the newly generated output files:
```
ls -lh ../output_files/sigcomm23_eval/
```

### Processing Results for 50% capacity constraint

#### Data Processing

Process the simulation output to generate the CDF data required for Figure 16:
```
make process_50 
```
This will generate additional data files in the same output folder, specifically
`total_penalty_ratio_50_cdf.dat` and `diff_min_pod_capacity_50_cdf.dat`, which you can check:
```
ls -lh ../output_files/sigcomm23_eval/
```

#### Plotting Graphs

Finally plot the Figures 15 and 16 with the data for 50% capacity constraint:
```
make plot_50
```

This will produce three PDF files, namely `figure15.pdf`, `figure16a.pdf` and
`figure16b.pdf`, located in the current directory (`sigcomm23-ae`). You can
compare these figures with the original figures in the paper for the 50%
capacity constraint.


### Simulations for 75% capacity constraint
> **Warning**
> This step requires ~7-8 hours of running time. It is optional and only required
> for full reproducibility. Feel free to [skip ahead to trace generation](#trace-generator).

Run the simulations for 75% capacity constraint in parallel:
```
make simulate_75_parallel
```
This parallel target for Make creates two independent instances of the simulator
and runs the simulation for CorrOpt and LinkGuardian + CorrOpt in parallel.
While it suppresses the output on stdout, you can still check (only read)
the log files in the output folder:
```
ls -lh ../output_files/sigcomm23_eval/*75.log
```

#### Data Processing

Once the simulations complete, you could then process the output files to generate the CDF data required for Figure 16:
```
make process_75 
```
This will generate additional data files in the same output folder, specifically
`total_penalty_ratio_75_cdf.dat` and `diff_min_pod_capacity_75_cdf.dat`, which you can check:
```
ls -lh ../output_files/sigcomm23_eval/
```

#### Plotting Graphs

Finally plot the *complete* Figures 15 and 16 with data for both 50% and 75% capacity constraints:
```
make plot_all
```

This will produce three PDF files, namely `figure15.pdf`, `figure16a.pdf` and
`figure16b.pdf`, located in the current directory (`sigcomm23-ae`). These
figures should fully match with the original figures in the paper. 

### Trace Generator

The trace generator uses an input JSON file that mainly specifies the network
topology, the distribution of loss rates, and mean time to failure (MTTF) for a
link. The trace used in our evaluation was generated using the input file
located at:
```
../trace_generator/input_files/sigcomm23_eval/fbfabric_100k_os1_mttf10k.json
```

Now, let's check the trace generator by generating a *new* trace using the same input file:
```
make generate_trace
```

This will generate a new trace file in the output folder which you can check:
```
ls -lh ../output_files/trace_gen_output/
```

The newly generated trace file should be similar in structure to the [main trace
file](../eval_traces/sigcomm23-eval/fbfabric_100k_os1_mttf10k-trace.json) used
in our evaluation. 

> **Note** 
> The trace generator uses entropy initialized (no seed) random number
> generators for per-link Weibull distributions. As a result, even though the
> same input file is used, each time a new trace is generated.
