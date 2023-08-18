# LinkGuardian Trace Generator

This directory includes the implementation of the trace generator as described in the
Appendix D of our [SIGCOMM'23 paper -
LinkGuardian](https://www.comp.nus.edu.sg/~bleong/publications/sigcomm23-linkguardian.pdf).

The trace generator takes as input the network topology (with its parameters), per-link MTTF
(Mean Time To Failure), and the distribution of loss rates.  as observed by Zhuo
et al. and described in the [SIGCOMM'17 paper -
CorrOpt](https://dl.acm.org/doi/10.1145/3098822.3098849) (Table 1). 

It then produces a trace of link failure events where each event is denoted as:
\<time\>, \<link id\>, \<loss rate\>. For example: `349200,6136,6.5e-05` denotes
that at time 349200 (seconds), link ID 6136 in the network topology started corrupting
packets with a loss rate of 6.5e-05.

The output trace file also contains the topology information for which the trace
was generated. This allows allows the simulator to check if the failure trace
being used was generated on the same network topology on which the simulation is
being run.

## Installation

The trace generator is also implemented in Python3 and requires the same
dependencies as the simulator. Please refer to the [main
README](../README.md#local-installation) for instructions on setting up the `lg-sim`
Python virtual environment.

## Usage

> **Note**
> All the steps below assume that you are in the `trace_generator`
> directory that contains the `generate_loss_trace.py` file. These steps have been
> tested and are expected to work on Ubuntu 18.04 and above.

Activate the `lg-sim` Python virtual environment:

```
conda activate lg-sim
```

Once the `lg-sim` environment is activated, it should show you a prefix to your
shell prompt as following:
```bash
(lg-sim) user@server:~/linkguardian-simulator/trace_generator$
```

Now, the trace generator can be run as following by providing a config JSON file
which consists of the required inputs for the trace:

```
./generate_loss_trace.py ./input_files/sigcomm23_eval/fbfabric_100k_os1_mttf10k.json
```

### Provided Input File
We provide the [input file](./input_files/sigcomm23_eval/fbfabric_100k_os1_mttf10k.json)
which was used to generate the link failure trace used in the evaluation. This
file uses:
1. A large [FB Fabric
topology](https://engineering.fb.com/2014/11/14/production-engineering/introducing-data-center-fabric-the-next-generation-facebook-data-center-network/)
consisting of ~100k switch-to-switch links.
2. The distribution of loss rates as
observed by Zhuo et al. and described in the [SIGCOMM'17 paper -
CorrOpt](https://dl.acm.org/doi/10.1145/3098822.3098849) (Table 1).
3. MTTF of 10,000 hours per-link which was the maximum MTTF as observed by Meza et al.
in their [IMC 2018 paper](https://dl.acm.org/doi/10.1145/3278532.3278566). 

This input file also specifies the maximum duration of the trace to be ~1 year.

### Output File
The trace generator produces the trace JSON file (`.json`) in the `output_dir` as specified in the
input JSON file.


> **Note** 
> The trace generator uses entropy initialized (no seed) random number
> generators for per-link Weibull distributions. As a result, even though the
> same input file is used, each time a slightly different trace is generated.
> However, the characteristics of the trace (e.g. failure interarrival times)
> remain similar across different runs using the same input file.