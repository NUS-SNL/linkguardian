# Setup Guidelines

Here we provide general guidelines on setting up your hardware for running LinkGuardian. We recommend using two physical Tofino1 switches and two physical servers. An additional switch can be used to emulate a larger topology.

We suggest using these setup guidelines in conjunction with the [SIGCOMM AE scripts and instructions](../sigcomm23-ae/README.md). 

### Topology Setup

Please refer to the following topology diagram for setting up your physical cabling. 

![AE Testbed](./linkguardian_ae_testbed.svg)
*Topology Diagram*

You may skip sw4, sw8 and sw10 which are formed using a third physical Tofino1 switch for a larger topology. In the above topology diagram, the numbering `a/b(c)` denotes the `a/b` front-panel port number and the
corresponding devport number `c`.

### Switch Setup


* **SDE Installation:** Install SDE 9.10.0 on one switch to run `sender.p4`. Install SDE 9.9.0 on another switch to run `receiver.p4`.

* **Helper Scripts:** Place the `p4_build.sh` and `run_pd_rpc.py` helper scripts from Intel within the SDE directory on both the switches. `run_pd_rpc.py` is especially important as it is used by our initial setup scripts.

* **CPU Interface:** Our setup scripts inject the initial dummy and explicit ACK packets through the CPU interface. Therefore, please initialize the SDE with the `bf_kpkt` driver that creates a network interface `ens1` on the switch control plane.

* **Topology-related changes:** Your topology will likely have different front-panel and devport numbers. Please adapt the `setup.py` scripts for both the sender and receiver switches accordingly.

### Server Setup

Our AE experiment scripts require a single sender and a single receiver. Therefore, two NIC interfaces either on the same server or on two different servers are required.

#### Server Configuration

LinkGuardian being a completely in-network solution does not have any specific hardware or software requirements on the server-side. Just that if you would like to run RoCEv2 workloads, RoCEv2-compatible NICs are required.

For reference, our experiments were run using servers with the following software configuration:

* Ubuntu 20.04.3 LTS
* Linux kernel 5.4.0-91-lowlatency
* MLNX_OFED_LINUX-5.4-1.0.3.0 (for 100G CX5 NIC):
    * driver: mlx5_core
    * version: 5.0-0
    * firmware-version: 16.35.2000 (MT_0000000012)


#### Namespaces and addressing

Our experiments were run using two physical servers named **lumos** and **caelus**. The NIC interface on each server is put inside a network namespace called `lg`. The traffic is sent from IP address `10.2.2.1/24` on one server to IP address  `10.2.2.2/24` on another server. You would need to either adapt our experiment scripts to match your testbed setup OR adapt your testbed setup to match our scripts.

