#!/bin/bash

# clear the screen, set the loss rate, check the status
ssh tofino1c-ae "tmux send-keys -t bfrt.0 C-l 'disable_pkt_dropping()' ENTER 'check_receiver_state()' ENTER"

