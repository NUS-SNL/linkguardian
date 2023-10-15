#!/bin/bash
rm -rf ./log/*.log
mkdir -p ./log
cmake .; make
