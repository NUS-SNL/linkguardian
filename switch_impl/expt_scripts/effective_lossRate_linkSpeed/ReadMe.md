


### IMP pre-experiment changes:
1. Increase the buffer on dummy next hop port on Rx
`tm.set_q_app_pool_usage(52, 0, pool=4, base_use_limit=1500, dynamic_baf=9, hysteresis=32)` 
2. Decrease the buffer on protected port on Tx
`tm.set_q_app_pool_usage(32, 0, pool=4, base_use_limit=200, dynamic_baf=9, hysteresis=32)`
3. On Tx, make sure traffic gen pkt size is correct to 1 TCP/IP MTU. The timer can remain as the one set for 100G.
4. Make sure forwarding ahead devport 52 on tofino1c is connected somewhere and is UP.

