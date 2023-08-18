# LinkGuardian SIGCOMM'23 AE (switch implementation)

## Overview

The goal of this AE submission is to show that the switch implementation
artifact of LinkGuardian is *functional*. To that end, we provide scripts and
instructions to run *key* experiments from [our paper](https://rajkiranjoshi.github.io/files/papers/sigcomm23-linkguardian.pdf) on a real hardware testbed
and produce *qualitatively* similar results in a reasonable amount of
time.

This README will guide you through the evaluation process which consists of the following steps:
1. Understanding and accessing the testbed setup (5 minutes)
2. Compiling the P4 source code using Intel P4Studio (3-4 minutes)
3. Running switch-to-switch stress test experiment (3-4 minutes)
4. Running the TCP FCT experiment (18-20 mins)
5. Running the RDMA FCT experiment (TBA)
6. Running the throughput experiment ()


### System Requirements
This AE guide requires a testbed consisting of 2 server hosts and 3 Tofino1
switches.

<!-- Specifically, as shown in Figure 7 in the
[paper](https://www.comp.nus.edu.sg/~bleong/publications/sigcomm23-linkguardian.pdf),
this guide requires hosts h4 and h8 that are connected via switches sw8, sw4,
sw2, sw6, and sw10. Among these, as shown in Figure 7, sw2 is the LinkGuardian
sender switch while sw6 is the LinkGuardian receiver switch. -->
#### Testbed for artifact evaluation

To make it easy for the evaluators, we have setup the required testbed for
this artifact evaluation. We will communicate with the evaluators over HotCRP
about remotely accessing the testbed. In particular, we will be making the
following arrangements:
* We will be providing remote ssh access to our testbed consisting of two x86_64
physical servers and three Intel Tofino1 switches. 
* The evaluators will share a common user account with username `sigcomm23ae`. 
* At a given time, only a single evaluator will be able to run the evaluation.
We appreciate the coordination among the evaluators to *time-share* the testbed.


#### Code of Conduct
Nearly all experiments involved in this artifact evaluation require sudo access
to the switches as well as the servers. It is therefore impossible for us to put
in place any access restrictions (e.g. chroot jail) without affecting the
ability to evaluate this artifact. We therefore ***trust*** that the evaluators
will abide by the simple code of conduct that they will use this remote access
with sudo privileges for the ***sole purpose*** of evaluating this artifact.
They will not indulge in any unethical practices including but not limited to
installing trojans, disrespecting the privacy and confidentiality of other user
accounts, copying/distributing the licensed Intel P4Studio SDE, etc.

> [!IMPORTANT] 
> By signing up to evaluate this artifact submission, you are agreeing to abide
> by this code of conduct. This is a requirement by our IT department.


## Artifact Evaluation Process

### Understanding and accessing the testbed setup

The following figure shows the testbed setup that we have prepared for the
artifact evaluation.

![AE Testbed](../doc/linkguardian_ae_testbed.svg)

This corresponds to the path h4-sw8-sw4-sw2-sw6-sw10 shown in Figure 7 in
[our paper](https://rajkiranjoshi.github.io/files/papers/sigcomm23-linkguardian.pdf). There are two physical servers, lumos and caelus, representing h4 and
h8 respectively. Each server is equipped with a 100G NVIDIA Mellanox CX5 100G
NIC interface that is put inside a network namespace called `lg`. There are a
total of three Tofino1 switches:
 * tofino1a --> sw2. Runs the LinkGuardian sender implementation (`sender.p4`)
 * tofino1c --> sw6. Runs the LinkGuardian receiver implementation (`receiver.p4`)
 * p4campus-proc1 --> emulates the rest of the physical topology (sw8, sw4, and sw10)
   through 100G loopback cables (`topo.p4`)

The numbering `a/b(c)` denotes the `a/b` front-panel port number and the
corresponding devport number `c`.

> [!NOTE] 
> The evaluation setup used in the paper used a variable optical attenuator
> (VOA) which requires manual setting of the loss rate through physical access
> to the VOA. Since physical access is not possible in a remote evaluation
> setting, to facilitate easy setting of the loss rate, in this artifact
> evaluation, we instead use Tofino-based random packet dropping that occurs on port
> `21/0(36)` on tofino1c *before* the packets are processed by the LinkGuardian
> receiver implementation.


Beyond the physical cabling and setup, there are several steps involved in
setting up the required software environment on the server and the switches which we
have detailed in the [setup guidelines document](../doc/setup_guidelines.md).
For the convenience of evaluators, we have already setup the required software
environment:
* The 100G NIC interfaces on lumos and caelus are placed inside a network
  namespace called `lg` and assigned the IP addresses `10.2.2.1/24` and
  `10.2.2.2/24` respectively.
* The P4 programs are compiled, loaded and configured with the one-time control
  plane configuration on all the switches. The one-time configuration includes
  the initialization of the self-replenishing queues, the forwarding rules to
  forward packets between lumos and caelus, etc.
* On each switch, we have configured two [tmux](https://github.com/tmux/tmux) sessions named
  `driver` and `bfrt`. The `driver` session is running the `switchd` program. On
  the other hand, the `bfrt` session is running a `bfrt_python` shell providing
  you with a CLI interface to interact with LinkGuardian sender and the
  receiver. However, you won't be required interact manually with the
  `bfrt_python` shell as we have provided several automation scripts (see below).


#### Access and terminal setup
You will have ssh access to lumos which will also serve as a ssh jumphost
allowing you access to caelus and the switches. We will provide you with a
ssh config file (over HotCRP) for easy access through the jumphost.

For terminal setup, please open your terminal application and setup three terminal tabs as
follows.

**Terminal Tab 1:** ssh connection to lumos for running AE experiment scripts

You will use this tab to run all the experiments as well as analyze the
experiment data.

```
ssh lumos-ae
```
Once you have logged into lumos successfully, change your directory to `expt_scripts-ae`:
```
cd ~/linkguardian/switch_impl/sigcomm23-ae/expt_scripts-ae
```

> [!NOTE]
> All the subsequent instructions for compiling source code and running the
> experiments assume that you are in the expt_scripts-ae
> directory on lumos.

**Terminal Tab 2:** ssh connection to tofino1a (LinkGuardian sender switch) 

You will use this tab mainly to *observe* the LinkGuardian sender switch while
running the experiments.

```
ssh tofino1a-ae
```
Once you have logged into the tofino1a successfully, connect to the tmux session
`bfrt` to access the bfrt_python CLI for the LinkGuardian sender switch.
```
tmux a -t bfrt
```
On the CLI, run the following command to check the status of the sender switch:
```
check_sender_state()
```
This should produce an output *similar* to the following which contains different
debugging and status information.
```
In [1]: check_sender_state()
Next seq no: 0
Next seq era: 0
leading_ack: 0
leading_ack_era: 0
ig_debug_counter: 0
eg_debug_counter: 44086994

corruption_seq_no (egress pkt counter): 0
emulated_corruption_counter (pkts dropped): 0

Emulated holes: 0
Corrupting Port(s) (0): 
Protected Port(s) (1): 32(0)
No. of reTx copies: 2

ECN Marking Threshold: 100.0KB (1250 cells)
```
This output check is only to verify that you have configured the second terminal tab
correctly.

**Terminal Tab 3:** ssh connection to tofino1c (LinkGuardian receiver switch) 

You will use this tab mainly to *observe* the LinkGuardian receiver switch while
running the experiments. 

```
ssh tofino1c-ae
```
Once you have logged into the tofino1c successfully, connect to the tmux session
`bfrt` to access the bfrt_python CLI for the LinkGuardian receiver switch.
```
tmux a -t bfrt
```
On the CLI, run the following command to check the status of the receiver switch:
```
check_receiver_state()
```
This should produce an output *similar* to the following which contains different
debugging and status information.
```
In [1]: check_receiver_state()

expected_seq_no: 0
ack (time_remaining): 0 (70)
ack_era: 0
leading_ack: 0
leading_ack_era: 0
leading_ack_notify_count: 0
ig_debug_counter: 0
eg_debug_counter: 219702974
timeout_pkt_no_trigger_cntr: 170068471
timeout_pkt_trigger_cntr: 0
LOSS RATE: 0.000000e+00


PFC resume threshold: 460 cells
PFC pause threshold: 500 cells
PFC curr state: 0
PFC PAUSE frames requested: 0
PFC RESUME frames requested: 0
PFC PAUSE frames sent: 0
PFC RESUME frames sent: 0
PFC gen frames dropped: 172060567
PFC gen on loss noti enabled: False (N/A cells)


lack_updates_sent_for_mirroring: 0
lack_updates_received_after_mirroring: 0
```
This output check is only to verify that you have configured the third terminal tab
correctly.


### Compiling the P4 source code

On lumos (terminal tab 1), given that you are inside the directory
`~/linkguardian/switch_impl/sigcomm23-ae/expt_scripts-ae`, run the following
command to compile the P4 source code:
```
./compile_p4_src.sh
```

This will compile the P4 programs `sender.p4`, `receiver.p4`, and `topo.p4` on
the respective Tofino1 switches (see the above figure). You should be able to
see the P4Studio compilation output on lumos itself (terminal tab 1).


### Running switch-to-switch stress test

The goal here is to run the stress test corresponding to Figure 8 of the paper.
Specifically, we will do the following steps in order:
1. Set the loss rate on tofino1c to around 10<sup>-3</sup>.
2. Using pktgen, send 100 million packets from tofino1a to tofino1c on the corrupting link
   (link 3 in the figure above) while running LinkGuardian and observe the
   effective loss rate (in terminal tab 2 i.e. tofino1a CLI).
3. Repeat step 2 above with LinkGuardianNB and again observe the effective loss
   rate (in terminal tab 2 i.e. tofino1a CLI).
4. Process the other data collected during steps 2 and 3, and compute the
   overall results including the effective link speed (Figure 8) as well as packet buffer
   overheads (Figure 14).

To set the random drop loss rate, run the following command on lumos (terminal
tab 1):
```
./common/enable_pkt_dropping.sh
```

Then observe the status of the receiver switch (tofino1c) in terminal tab 3. You
should see an output which includes the following line:
```
....
LOSS RATE: 9.994507e-04
....
```

Now, run the stress test for LinkGuardian:
```
./effective_lossRate_linkSpeed/run_expt.sh 10-3_lg 1
```
This will start the stress test experiment with 100M packets in total. You can
monitor the progress on terminal tab 2 i.e. tmux session `bfrt` on tofino1a. 

The experiment will finish with the following output on the `bfrt_python` shell:
```
.....
Copying files from Tx switch... Done
Copying files from Rx switch... Done
```

Now, let's run the same stress test for LinkGuardianNB with the following
command on lumos:
```
./effective_lossRate_linkSpeed/run_expt.sh 10-3_lg_nb 0
```

At the end of each experiment all the data files from the switches
are already copied to lumos. You can check them here (the timestamps are in
Singapore time i.e. UTC+8):
```
ll effective_lossRate_linkSpeed/*.log effective_lossRate_linkSpeed/*.dat
```

Now, let's analyze the data from both the experiments:

```
./effective_lossRate_linkSpeed/analyze_both_expts.sh
```

You should see an output like the following:
```
                                 10-3_lg (blocking)
-------------------------------  --------------------
Actual Loss Rate                 9.970e-04
Effective Loss Rate              0.000e+00
Effective Link Speed             92.25 Gbps
TX Buffer Occupancy (min - max)  0.0 - 41.76 KB
RX Buffer Occupancy (min - max)  0.0 - 83.6 KB

                                 10-3_lg_nb (non-blocking)
-------------------------------  ---------------------------
Actual Loss Rate                 1.000e-03
Effective Loss Rate              0.000e+00
Effective Link Speed             98.74 Gbps
TX Buffer Occupancy (min - max)  4.8 - 22.8 KB
```
While this artifact evaluation is NOT geared towards reproducibility, the
results here should still be similar to those reported in the paper (Figures 8
and 14), except for the effective loss rate. The effective loss rate that you
would observe will mostly be zero since we are sending only 100M packets (in the
interest of time/convenience) while LinkGuardian's expected effective loss rate
is around 10<sup>-9</sup>. Note that the experiments in the paper report the
results across multiple runs where a total of 10B packets are sent. 

### Running the TCP FCT experiment
The goal here is to run the flow completion time (FCT) experiment for 24,387B
TCP flows using DCTCP transport (Figure 11(a)).
Specifically, we will do the following steps in order:
1. We will enable packet dropping on link 3 (figure above) with a loss rate of 10<sup>-3<sup>.
2. We will then run 3 experiments: (i) without any protection on the link, (ii)
   enabling LinkGuardian on the link, (iii) enabling LinkGuardianNB on the link.
   We will run 5K flow trials for each experiment.
3. We will analyze the packet traces (pcap files) from the above experiments to
   compute the FCTs and then observe the results.

Enable packet dropping first (default loss rate of 10<sup>-3<sup>):
```
./common/enable_pkt_dropping.sh
```
Disable LinkGuardian's protection:
```
./common/disable_protection.sh
```
You should see the following output on terminal tab 2 (sender switch's status):
```
....
Protected Port(s) (0): 
....
```
This means that the number of protected ports by LinkGuardian is zero.

Now, let's run 5K flows trials. The command below will run 5 runs, each run
consisting of 1K flow trials:
```
./fct_expt_tcp/run_expt.sh 10-3 5
```
You should see the progress of the experiment as following:
```
[Run: 2] Sending flow 17 ...
[Run: 2] Sending flow 18 ...
[Run: 2] Sending flow 19 ...
[Run: 2] Sending flow 20 ...
[Run: 2] Sending flow 21 ...
```
This should take around 5 mins.

Once the experiment is over, enable LinkGuardian on the link:
```
./common/enable_protection.sh 1
```
You should see the following output on terminal tab 2 (sender switch's status):
```
...
Protected Port(s) (1): 32(1)
...
```
This means that the number of protected ports by LinkGuardian is 1.`32(1)` means
that LinkGuardian is maintaining packet ordering on devport 32.  

Now, again run 5K flow trials:
```
./fct_expt_tcp/run_expt.sh 10-3_lg 5
```

Once the experiment is over, enable LinkGuardianNB on the link:
```
./common/enable_protection.sh 0
```
You should see the following output on terminal tab 2 (sender switch's status):
```
...
Protected Port(s) (1): 32(0)
...
```
This means that the number of protected ports by LinkGuardian is 1.`32(0)` means
that LinkGuardianNB is running on devport 32 and packet ordering will not be
maintained.

Now, again run 5K flow trials:
```
./fct_expt_tcp/run_expt.sh 10-3_lg_nb 5
```

Now, let's process the data from all 3 experiments and compute the FCTs:
```
./fct_expt_tcp/process_all_expts.sh
```

Once the data processing is over, you can view the combined result of all 3
experiments with the following command:
```
./fct_expt_tcp/display_combined_result.sh
```

This should should show a descriptive FCT distribution for all the 3
experiments like the following:
```
             10-3   10-3_lg  10-3_lg_nb
min        65.418    69.251      64.417
mean      124.812   121.334     120.780
50%       124.293   125.210     124.585
90%       128.006   140.964     143.848
95%       134.626   159.129     159.543
99%       166.673   162.293     167.382
99.9%    3100.882   176.044     200.637
99.99%   3891.492   190.711     273.385
99.999%  3926.529   190.749     305.404
max      3930.422   190.753     308.962
std       144.750    19.528      20.797
count    5000.000  5000.000    5000.000
```

This result should be qualitatively similar to that presented in the paper and should show a clear reduction in the tail FCTs with LinkGuardian and LinkGuardianNB. 

### Running the RDMA FCT experiment
TBA: We are in the process of setting up the RDMA sender/receiver in the AE testbed setup. We will update this section soon!


### Running the throughput experiment

The goal here is to run the throughput test corresponding to Table 3 of the paper.
Specifically, we will do the following steps in order:
1. We will change the speed of all links to 10G (figure above). This will allow
   a single TCP sender to easily saturate the entire link speed.
2. We will enable packet dropping on link 3 (figure above) with a loss rate of
   10<sup>-3<sup>.
3. We will then run 3 throughput experiments: (i) without any protection on the
   link, (ii) enabling LinkGuardian on the link, (iii) enabling LinkGuardianNB
   on the link. We will run each experiment for 70s with CUBIC as the congestion
   control and look at the steady state average throughput during the middle
   60s.

Change the link speeds of all links to 10G:
```
./common/change_link_speeds.sh 10
```
This script will also wait and check if the links have come UP with 10G link
speeds.

Now, reset the counters and other state on all the switches for a fresh
experiment environment:
```
./common/reset_all_switches.sh
```

Check the connectivity between lumos_lg and caelus_lg:
```
./common/check_connectivity.sh
```
The ping request-response packets should show connectivity. It is possible that some ping
packets might get dropped in case packet dropping is already enabled on link 3.

Make sure that packet dropping is enabled on link 3 (default loss rate of 10<sup>-3<sup>):
```
./common/enable_pkt_dropping.sh
```
You can check the terminal tab 3 (receiver switch's status) to verify that the
packet dropping has been enabled:
```
...
LOSS RATE: 9.994507e-04
...
```

Disable LinkGuardian's protection:
```
./common/disable_protection.sh
```

You should see the following output on terminal tab 2 (sender switch's status):
```
....
Protected Port(s) (0): 
....
```
This means that the number of protected ports by LinkGuardian is zero.

Now, let's run the throughput experiment. The command below will run a CUBIC flow for 70s:
```
./throughput_expt/run_expt.sh 10-3
```
You should see the progress of the experiment as following:
```
...
*** Starting flow from lumos... 
```
This should take around 90 seconds to finish.

Once the experiment is over, enable LinkGuardian on the link 3:
```
./common/enable_protection.sh 1
```
You should see the following output on terminal tab 2 (sender switch's status):
```
...
Protected Port(s) (1): 32(1)
...
```
This means that the number of protected ports by LinkGuardian is 1.`32(1)` means
that LinkGuardian is maintaining packet ordering on devport 32.  

Now, again run the throughput experiment:
```
./throughput_expt/run_expt.sh 10-3_lg
```

Once the experiment is over, enable LinkGuardianNB on the link:
```
./common/enable_protection.sh 0
```
You should see the following output on terminal tab 2 (sender switch's status):
```
...
Protected Port(s) (1): 32(0)
...
```
This means that the number of protected ports by LinkGuardian is 1.`32(0)` means
that LinkGuardianNB is running on devport 32 and packet ordering will not be
maintained.

Now, again run the throughput experiment:
```
./throughput_expt/run_expt.sh 10-3_lg_nb
```

Now, let's process the data from all 3 experiments and compute the FCTs:
```
./throughput_expt/process_all_expts.sh
```

This should show you the final result of the throughput experiments like the
following:
```
 expt_name	avg_throughput(Gbps)
      10-3	2.77
   10-3_lg	9.45
10-3_lg_nb	9.45
```

