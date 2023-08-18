# corruptd

This is the link monitoring daemon to detect corrupted links.
We continuously poll the switch TX/RX statistics to identify corrupted links.

## Dependencies
First, install the necessary dependencies by doing `pip3 -r requirements.txt`.
We recommend using the Python3 `virtualenv`.

Next, we assume that you have Docker Engine installed.

If not, for Ubuntu, following the installation guide [here](https://docs.docker.com/engine/install/ubuntu/) and make sure to apply the necessary post-install [steps](https://docs.docker.com/engine/install/linux-postinstall/).
Eventually, you should be able to launch the `hello-world` Docker container without the `sudo` command: `docker run hello-world`.

## Running corruptd

### Step 1: Run Redis
First, start Redis by doing `docker compose up`.
This can be done on any host.

### Step 2: Populate Redis with topology information
Next, populate Redis with the topology information.
Do `python3 setup.py [see options]`. 
This can be done on any host.

See example under `sample/topo.json`, the format should be "local_switch_id,local_switchport : upstream_switch_id,upstream_switchport,upstream_switch_mcast_group".

### Step 3: Start corruptd.py
Finally, start corruptd by doing `python3 corruptd.py [see options]`.
Ideally, this should be started on the switch, but can also be on a remote host as long as it can reach the BfRT server.

> Note: corruptd_a (sender) and corrupt_c (receiver) are used for earlier experimentation which are derived from corruptd.py. They are included as reference.

<!-- ## Known Issues -->
<!-- 1. bfrt action data all 0, not showing correct values (same for bfrt python) -->
<!-- 2. TBDstill needs integration and testing -->