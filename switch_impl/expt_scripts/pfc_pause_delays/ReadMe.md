# Measuring PFC Flight Delays
## Preparation Setup
0. Compile receiver using -DMEASURE_PFC_DELAYS=1
1. Tx: Disable dummy pkts on the sender (setup.py)
2. Tx: Decrease pktgen timer to 123ns such that queue builds up on the protect
   link (config_pktgen.py)
3. Rx: Increase pktgen timer to 10us for toggle sending of pause/resume (config_pktgen.py)
4. Tx: Decrease static queue limit on the protect link (avoid buffer pressure)
5. Rx: Disable ack timeout traffic in the beginning (setup.py)


## Steps for PFC delays measurement
0. Tx: nb-mode protection. Rx: No dropping.
1. Tx: unlimit trafficGen
2. Tx: start traffic
3. Rx: start ack timeout traffic
4. Rx: stop ack timeout traffic
5. Tx: stop traffic
6. Collect data

```
On Rx:
reset_all_pfc_measurement_state()

On tx:
start_traffic()

On Rx:
start_ack_timeout_traffic()
// wait 1-2 seconds
stop_ack_timeout_traffic()

On Tx:
stop_traffic()

On Rx: collect and dump data
get_pfc_delay_ts()
dump_pfc_delay_ts_values(pfc_delay_ts_list, 3)

```
