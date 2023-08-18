# ReTx Latency Measurement

1. Compile both sender and receiver with `-DMEASURE_RETX_LATENCY=1`
2. Modify config_pktgen.py to reduce static queue size before the protected port
3. On Rx: set the random loss rate
4. On Tx: set non-blocking mode and adjust the reTx copies as per the loss rate
5. Clear port counters on receiver (helps to see how much experiment has
   progressed)
6. Set `rate-period 1` on Rx ucli and check `rate-show` during the experiment
