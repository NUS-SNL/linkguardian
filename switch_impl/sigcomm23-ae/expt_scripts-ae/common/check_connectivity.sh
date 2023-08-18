#!/bin/bash

sudo ip netns exec lg env LANG=en ping 10.2.2.2 -c 5 -i 0.2

