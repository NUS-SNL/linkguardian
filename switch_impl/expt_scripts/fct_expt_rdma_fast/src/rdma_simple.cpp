/*
	Copyright (C) 2023 Chahwan Song, National University of University
    skychahwan [at] gmail.com
    
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.
    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
*/

#include <getopt.h>

#include "common.hpp"

using namespace rdma_simple;

#define DEFAULT_NUM_RUNS 100000

void usage() {
    std::string default_logfile_path(__FILE__);
    replace(default_logfile_path, std::string("/src/rdma_simple.cpp"), std::string("/log/test.log"));

    printf("---Usage---\n");
    printf("rdma: \n[-s <server_ip>] : Running server program \n[-c <server_ip>] : Running client program \n[-p <server_port>]\n[-m <message_size>]\n[-l <logfile_path>]\n");
    printf("[REQUIRED] server_ip is required\n");
    printf("[DEFAULT] server_port is %d \n", DEFAULT_RDMA_PORT);
    printf("[DEFAULT] message size is %d \n", DEFAULT_MESSAGE_SIZE);
    printf("[DEFAULT] logfile path is %s \n", default_logfile_path.c_str());
    printf("[DEFAULT] num_runs is %d \n", DEFAULT_NUM_RUNS);
}

int main(int argc, char **argv) {
/* ignore warning message by strncpy() */
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wstringop-overflow"

    int option;
    int num_runs = 0;
    bool rdma_server = false, rdma_client = false, rdma_port = false,\
     size_input = false, logfile_input = false, num_runs_input = false;
    char *server_ip, *server_port, *msg_size, *logfile_path;
    while ((option = getopt(argc, argv, "s:c:p:m:hl:n:")) != -1) {
        switch (option) {
            case 's':
                rdma_server = true;
                printf("[Server] Passed SERVER's ip is : %s \n", optarg);
                server_ip = (char *)calloc(strlen(optarg), 1);
                strncpy(server_ip, optarg, strlen(optarg));
                break;
            case 'c':
                rdma_client = true;
                printf("[Client] Passed SERVER's ip is : %s \n", optarg);
                server_ip = (char *)calloc(strlen(optarg), 1);
                strncpy(server_ip, optarg, strlen(optarg));
                break;
            case 'p':
                rdma_port = true;
                printf("Passed port is : %s \n", optarg);
                server_port = (char *)calloc(strlen(optarg), 1);
                strncpy(server_port, optarg, strlen(optarg));
                break;
            case 'm':
                size_input = true;
                printf("Passed msg size is : %s \n", optarg);
                msg_size = (char *)calloc(strlen(optarg), 1);
                strncpy(msg_size, optarg, strlen(optarg));
                break;
            case 'l':
                logfile_input = true;
                printf("Passed logfile path is : %s \n", optarg);
                logfile_path = (char *)calloc(strlen(optarg), 1);
                strncpy(logfile_path, optarg, strlen(optarg));
                break;
            case 'n':
                num_runs_input = true;
                num_runs = atoi(optarg);
                printf("Passed num_runs is : %d \n", num_runs);
                break;
            default:
                usage();
                return 0;
        }
    }

    /* catch parsing error */
    if (rdma_server + rdma_client != 1) {
        printf("ERROR - Only either one of -s or -c should be specified.\n\n");
        usage();
        exit(1);
    }

    if (!rdma_port) {
        std::string default_port = std::to_string(DEFAULT_RDMA_PORT);
        char const *pchar = default_port.c_str();
        server_port = (char *)calloc(strlen(pchar), 1);
        strncpy(server_port, pchar, strlen(pchar));
        printf("Use default port %s \n", server_port);
    }

    if (!size_input) {
        std::string default_size = std::to_string(DEFAULT_MESSAGE_SIZE);
        char const *pchar = default_size.c_str();
        msg_size = (char *)calloc(strlen(pchar), 1);
        strncpy(msg_size, pchar, strlen(pchar));
        printf("Use default msg size %s \n", msg_size);
    }

    if (!logfile_input) {
        std::string default_path(__FILE__);
        replace(default_path, "/src/rdma_simple.cpp", "/log/test.log");
        logfile_path = str_copy(default_path.c_str());
        printf("Using default logfile path %s \n", logfile_path);
    }

    if (!num_runs_input) {
        num_runs = DEFAULT_NUM_RUNS;
        printf("Using default num_runs %d \n", num_runs);
    }

#pragma GCC diagnostic pop

    int ret = 0;
    uint64_t n_conn = 0, n_run = 0;
    
    if (rdma_server) {
        printf("Start server\n");
        ServerRDMA r_server;
        while (true) {
            usleep(10000); // 0.01 sec retry delay 
            printf("*-*-*- Run %lu -*-*-*\n", n_conn++);
            
            ret = r_server.start(server_ip, server_port);
            if (!ret) continue;
            ret = r_server.send_server_metadata();
            if (!ret) continue;
            ret = r_server.disconnect_and_cleanup();
            if (!ret) continue;
        }
    }

    if (rdma_client) {
        printf("Start client\n");
        ClientRDMA r_client;
        FILE *client_output = NULL;
        char *client_output_file; 

        /** logging file directory */
        std::string filepath(__FILE__);
        client_output_file = logfile_path;

        while (true) {
            usleep(100000); // 0.1 sec retry delay
            printf("*-*-*- Run %lu -*-*-*\n", n_conn++);
            
            ret = r_client.start(server_ip, server_port);
            if (!ret) continue;
            ret = r_client.send_client_metadata();
            if (!ret) {
                ret = r_client.disconnect_and_cleanup();
                continue;
            }
            while (true) {
                ret = r_client.remote_memory_ops(IBV_WR_RDMA_WRITE, atoi(msg_size));  // IBV_WR_RDMA_WRITE, IBV_WR_RDMA_READ
                n_run++;
                if (!ret) {
                    ret = r_client.disconnect_and_cleanup();
                    continue;
                }
                printf("Measuring %lu-th flow is done.\n", n_run);

                /** stop condition */
                if (n_run >= num_runs) {
                    client_output = fopen(client_output_file, "w");
                    r_client.flush_fct_records(client_output);
                    printf("Results logged to file: %s \n", client_output_file);
                    r_client.disconnect_and_cleanup();
                    printf("======================    END   ======================\n");
                    exit(0);
                }
            }
            ret = r_client.disconnect_and_cleanup();
        }
    }
    printf("======================    END   ======================\n");
}
