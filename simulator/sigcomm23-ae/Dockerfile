FROM ubuntu:22.04
ARG DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y gnuplot python3 python3-pip && rm -rf /var/lib/apt/lists/*
RUN pip3 install pylint networkx ipython jupyter termcolor matplotlib tabulate pandas tqdm progress

WORKDIR /root