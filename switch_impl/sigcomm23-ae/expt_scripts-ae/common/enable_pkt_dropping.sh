#!/bin/bash

# clear the screen, set the loss rate, check the status
ssh tofino1c-ae "tmux send-keys -t bfrt.0 C-l 'drop_random_pkts(0.001)' ENTER 'check_receiver_state()' ENTER"

