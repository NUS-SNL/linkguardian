# LinkGuardian Simulator

This repository includes the simulator used in the evaluation of our [SIGCOMM'23
paper - 
LinkGuardian](https://www.comp.nus.edu.sg/~bleong/publications/sigcomm23-linkguardian.pdf)
(section 4.8). This open-source simulator is designed based on the closed-source
simulator used by Zhuo et al. and described in the [SIGCOMM'17 paper -
CorrOpt](https://dl.acm.org/doi/10.1145/3098822.3098849) (section 7.1).

If you haven't read our paper, we provide a brief summary of this simulator's design
[here](./doc/design.md "Design Summary").

## Installation and Usage

### Note for Artifact Evaluation
If you want to simply run the simulator for artifact evaluation, we provide a
convenient Docker container image. Please refer to the README and Makefile in
the [sigcomm23-ae/](./sigcomm23-ae/) directory.

If you want to have a local installation of the simulator, for example, to tweak
it or build on top of it, please continue reading.

### Local Installation

> **Note**
> All the steps below assume that you are in the root directory of this
> repository that contains the `main.py` file. These steps have been tested and are
> expected to work on Ubuntu 18.04 and above.

The simulator is implemented in Python3 and requires the following packages:
```
pylint networkx ipython jupyter termcolor matplotlib tabulate pandas tqdm progress
```

Instead of manually installing these packages, we recommend using a Python
virtual environment managed by `conda`. If you do not already have conda, we
recommend [installing it through Miniconda](https://conda.io/projects/conda/en/stable/user-guide/install/index.html)
which provides a minimal conda installation compared to Anaconda.

Once you have conda installed and available in your `$PATH`, you can create the
required Python virtual environment (called `lg-sim`) using the following
command (one-time step): 

```
conda env create -f ./conda_env-lg_sim.yml
```

### Local Usage

After the conda environment `lg-sim` is created, you can activate the same before running the simulator.

```
conda activate lg-sim
```

Once the `lg-sim` environment is activated, it should show you a prefix to your
shell prompt as following:
```bash
(lg-sim) user@server:~/linkguardian-simulator$
```

Now, the simulator can be run as following by providing a config JSON file which consists of the
required inputs for the simulator run:

```
./main.py ./simulation_configs/sigcomm23_eval/fbfabric_100k_os1-corropt_50.json
```

During a simulation run, the simulator first builds the topology (in-memory) and
then plays the failure trace while applying the specified solution.

### Output Files
Each simulator run produces two files in the `output_dir` as specified in the
simulation config file:
1. A data file (`.dat`) consisting of a timeseries of topology-level performance
parameters; and 
2. A log file (`.log`) showing the logs from the simulation run.


## Provided Simulation Configs and Failure Trace
We provide four different simulation configs used in our paper's evaluation
under [simulation_configs/sigcomm23_eval](./simulation_configs/sigcomm23_eval/).
The four configs result from the fact that we have two solutions (`CorrOpt` and
`LinkGuardian + CorrOpt`) each to be run with two capacity constraints (50% and
75%). 

All four configurations use a large [FB Fabric
topology](https://engineering.fb.com/2014/11/14/production-engineering/introducing-data-center-fabric-the-next-generation-facebook-data-center-network/)
consisting of ~100k switch-to-switch
links and a corresponding 1-year long link failure trace provided [here](./eval_traces/sigcomm23-eval/fbfabric_100k_os1_mttf10k-trace.json). 

## Trace Generation
The [trace](./eval_traces/sigcomm23-eval/fbfabric_100k_os1_mttf10k-trace.json)
that was used in our paper's evaluation was generated using the trace generator
provided in this repository and described in [our
paper](https://www.comp.nus.edu.sg/~bleong/publications/sigcomm23-linkguardian.pdf)
(Appendix D). Please refer to
[trace_generator/](./trace_generator/) for more details.



