#!/bin/bash

ssh tofino1a-ae "tmux send-keys -t bfrt.0 C-l 'disable_protection(32)' ENTER 'check_sender_state()' ENTER"

