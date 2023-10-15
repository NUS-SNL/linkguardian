# RDMA Traffic Generator

## Features
### Persistent RDMA Connections
In this project, we create a persistent connection in order to (1) avoid the idle time to create connection (e.g., handshaking and trading metadata), and (2) allow to maximize link utility and message generating rate.

:star: As we use persistent connection between client-server, there is no handshake or metadata communication before sending message.
This enables to achieve the maximum bandwidth saturation without an idle time.

### Flow Completion Time
We calculate flow completion time (a.k.a. FCT) from the time the first data is sent to the time the last data's ACK is received, which is a pretty standard way of FCT measurement in TCP. We monitor the timestamps at the application layer, putting a brick of code inside the RDMA implementation.

:exclamation: Note that inside the persistent connection, messages use same queue pair destination and addresses. This implies it may be difficult to distinguish messages. To hack this, we analyze the rdma code and put a timestamping code appropriately. Please refer to the code in `src/common.h`.

### Supported RDMA Operations
We support one-sided RDMA operations, e.g., `RDMA_WRITE` and `RDMA_READ`, but would be easy to support `RDMA_SEND` also by changing the `permission` in rdma source code (`/src/common.hpp`) and `op_code` in the script `/src/rdma_simple.cpp` (e.g., `IBV_WR_RDMA_WRITE`).
By default, we use `RDMA_WRITE` opcode.

## Quick start
### Compile with CMake
This project needs minimum version of CMake `>= 3.0`. 
```
cmake .
make clean; make;
```
Or, you can simply run `reset.sh`.

### First, Run Servers
```
./bin/rdma_server -s 10.2.2.2
```
Use `-h` to see help description.

### Next, Run Clients
```
./bin/rdma_client -c 10.2.2.2 -m 24387
```
Use `-h` to see help description. `-m` is the size of message. 

### Output
It runs 100K flows and measure the flow completion time based on QP completion event. 
The measurement result is saved in `/log/test.log`. First column is a message size, and second column is the FCT.

## Contact
* Chahwan Song [skychahwan@gmail.com](skychahwan@gmail.com)
