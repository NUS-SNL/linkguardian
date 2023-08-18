#!/bin/bash

cecho(){  # source: https://stackoverflow.com/a/53463162/2886168
    RED="\033[0;31m"
    GREEN="\033[0;32m"
    YELLOW="\033[0;33m"
    # ... ADD MORE COLORS
    NC="\033[0m" # No Color

    printf "${!1}${2} ${NC}\n"
}

rm -rf ./CMakeFiles
rm ./cmake_install.cmake
rm ./CMakeCache.txt
rm ./log/*
rm ./bin/*

cecho "RED" "Clear all files!!"
