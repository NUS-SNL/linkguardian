# LinkGuardian Switch Implementation

This repository provides the Intel Tofino-based switch dataplane implementation for our [SIGCOMM'23
paper -
LinkGuardian](https://www.comp.nus.edu.sg/~bleong/publications/sigcomm23-linkguardian.pdf). We also provide several scripts that could be
*adapted* for running the experiments from our paper on another testbed setup.

### Repository Contents
* `corruptd`: Control plane daemon to detect corruption and enable LinkGuardian.
* `data_analysis`: Scripts for analyzing the data from key experiments.
* `doc`: Additional supplementary documentation.
* `expt_scripts`: Scripts for running key experiments. 
* `sigcomm23-ae`: Detailed README for artifact evaluation and the corresponding
  scripts. 
* `system_impl`: The main dataplane implementation along with control plane
  config scripts.
  * `common`: common LinkGuardian headers (P4 src) and control plane scripts.
  * `receiver`: LinkGuardian's receiver switch implementation (`receiver.p4`) and
    control plane config scripts. Tested with Intel P4Studio SDE 9.9.0.
  * `sender`: LinkGuardian's sender switch implementation (`sender.p4`) and
    control plane config scripts. Tested with Intel P4Studio SDE 9.10.0.
* `topo_impl`: Multi-switch physical topology implementation on top of a
    single Tofino switch. Also includes corresponding control plane scripts.
  

### System Requirements
To run the provided artifacts "as is", the following are the *minimal* hardware
requirements:
* Two Tofino1 switches for running `sender.p4` and `receiver.p4`.
  * An additional Tofino1 switch would be required for creating the multi-switch
    physical topology (Figure X in the paper).
* One server with a dual port NIC for sending end-host traffic.
  * Each NIC port can be placed in a separate network namespace to emulate a
    sending and a receiving host.
  * Additional servers/NICs can be added for larger topology.

### SIGCOMM'23 Artifact Evaluation

Please refer to [sigcomm23ae/README.md](./sigcomm23-ae/README.md) for detailed
instructions and top-level scripts for SIGCOMM'23 artifact evaluation.


