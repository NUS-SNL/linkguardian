### Simulator Design Summary
The simulator is event-driven (single threaded) and operates at the level of a
large datacenter network topology. It takes the following inputs which are
specified through a JSON input file:

1. **Topology:** the topology type (e.g. FB Fabric) along with its parameters.
2. **Link failure trace:** a trace containing link failure events where each
event is denoted as: \<time\>, \<link id\>, \<loss rate\>. For example:
`349200,6136,6.5e-05` denotes that at time 349200, link ID 6136 in the network
topology started corrupting packets with a loss rate of 6.5e-05.
3. **Solution:** The solution could either be
   [CorrOpt](https://dl.acm.org/doi/10.1145/3098822.3098849) which is an
   algorithm to disable a subset of the failed links or it could be the joint
   strategy of `LinkGuardian + CorrOpt` as proposed in [our
   paper](https://www.comp.nus.edu.sg/~bleong/publications/sigcomm23-linkguardian.pdf)
   (section 3.6). Any parameters corresponding to the solution are also required
   as the input; most importantly, the "capacity constraint" as per which the
   solution needs to operate.

The simulator then outputs a timeseries of several topology-level performance
parameters, most important of which are the following:
1. **Total penalty:** sum of the loss rates for all the active (remaining) corrupting
links in the network. 
2. **Least paths per ToR:** the least fraction of paths to the spine
(top) layer of the network for the worst-case ToR. This metric
captures the impact on per-ToR path diversity as corrupting
links are disabled for repair.
3. **Least capacity per pod:** the total capacity in a network pod from
the ToR-layer to the spine (top) layer for the worst-case pod in the
network.

