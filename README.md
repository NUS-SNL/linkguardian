# LinkGuardian

LinkGuardian is a system to mitigate the impact of corruption packet losses in datacenter networks through link-local retransmission in the network dataplane.
LinkGuardian runs as a protocol between two adjacent switches to detect and recover corruption packet losses at sub-RTT timescales. Our [SIGCOMM 2023 paper](https://rajkiranjoshi.github.io/files/papers/sigcomm23-linkguardian.pdf) describes the system in more detail.

This repository provides the system implementation of LinkGuardian on top of the Intel Tofino switch. It also provides the simulator that we built for large-scale topology-level simulations.

## Repository Structure

### Simulator

The [simulator/](./simulator/) directory provides the simulator implementation and is further structured as following:

`simulator/`
* `data_analysis`: Scripts for analyzing simulation experiment results.
* `doc`: Additional documentation.
* `eval_traces/sigcomm23-eval`: Evaluation traces used in our SIGCOMM'23 paper.
* `sigcomm23-ae`: Detailed README for artifact evaluation along with Dockerized simulator and graph plotting scripts.
* `simulation`, `solutions`, `topology`, `utils`, `main.py`: The main simulator source code.
* `simulation_configs/sigcomm23_eval`: The simulation configurations used in our SIGCOMM'23 paper.
* `trace_generator`: The implementation of the trace generator as described in Appendix D of our SIGCOMM'23 paper.
* `conda_env-lg_sim.yml`: Conda environment file to setup the required Python environment. 

### System Implementation

The [switch_impl/](./switch_impl/) directory provides the system implementation of LinkGuardian on top of the Intel Tofino switch and is further structured as following:

`switch_impl/`
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

### README Files
Both the [simulator/](./simulator/) and the [switch_impl/](./switch_impl/) directories contain their respective README files with further details on system requirements and instructions to exercise the artifacts.


## SIGCOMM'23 Artifact Evaluation

For our SIGCOMM'23 paper, there are two artifacts to be evaluated: the [simulator/](./simulator/) and the [switch_impl/](./switch_impl/). Both artifacts can be evaluated independently by following the provided AE README files:
* [Simulator AE README](./simulator/sigcomm23-ae/README.md) (Expected time: ~1 hr)
* [Switch Implementation AE README](./switch_impl/sigcomm23-ae/README.md) (Expected time: ~1 hr)

---
### Citation
```
@inproceedings{joshi2023linkguardian,
  title={Masking Corruption Packet Losses in Datacenter Networks with Link-local Retransmission},
  author={Joshi, Raj and Song, Cha Hwan and Khooi, Xin Zhe and Budhdev, Nishant and Mishra, Ayush and Chan, Mun Choon and Leong, Ben},
  booktitle={Proceedings of SIGCOMM},
  year={2023}
}
```
### License
```
MIT License

Copyright (c) 2023 National University of Singapore

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
