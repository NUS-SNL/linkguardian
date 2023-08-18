#!/bin/bash

ssh tofino1a-ae "tmux send-keys -t bfrt.0 C-l 'reset_all()' ENTER 'check_sender_state()' ENTER"
ssh tofino1c-ae "tmux send-keys -t bfrt.0 C-l 'reset_all()' ENTER 'check_receiver_state()' ENTER"
ssh p4campus-proc1-ae "tmux send-keys -t bfrt.0 C-l 'reset_all()' ENTER 'check_status()' ENTER"
