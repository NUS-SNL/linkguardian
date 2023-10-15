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

#pragma once
#include <arpa/inet.h>
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <getopt.h>
#include <infiniband/verbs.h>
#include <inttypes.h>
#include <limits.h>
#include <netdb.h>
#include <netinet/in.h>
#include <rdma/rdma_cma.h>
#include <rdma/rdma_verbs.h>
#include <signal.h>
#include <stdint.h>  // for uint64_t
#include <stdio.h>
#include <stdio.h>  // for printf
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>  // for high-resolution timestamping
#include <unistd.h>

#include <exception>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

#include "macro.hpp"
namespace rdma_simple {

/******************/
/* RDMA CONSTANTS */
/******************/
/* Default port where the RDMA server is listening */
#define DEFAULT_RDMA_PORT (20886)
/* Capacity of the completion queue (CQ) */
#define CQ_CAPACITY (32)
/* MAX SGE capacity */
#define MAX_SGE (1)
/* MAX work requests */
#define MAX_WR (32)
/* XXX: Default number of SGE (scatter/gatter element) */
#define NUM_SGE (1)
/* Time to wait for resolution to complete at client (ms) */
#define RESOLVE_TIMEOUT (100)
/* How many outstanding requests to handle */
#define INITIATOR_DEPTH (5)
/* How many outstanding requests we expect other side to handle */
#define RESPONDER_RESOURCES (3)
/* Client's retry count */
#define RETRY_COUNT (5)
/* Maximum data len */
#define MAX_DATA_LEN (1024 * 1024 * 30)

/* Concat Strings */
char *concat(const char *s1, const char *s2) {
    char *result = (char *)malloc(strlen(s1) + strlen(s2) + 1);  // +1 for the null-terminator
    // in real code you would check for errors in malloc here
    strcpy(result, s1);
    strcat(result, s2);
    return result;
}

/* Replace Strings */
bool replace(std::string &str, const std::string &from, const std::string &to) {
    size_t start_pos = str.find(from);
    if (start_pos == std::string::npos)
        return false;
    str.replace(start_pos, from.length(), to);
    return true;
}

/* Copy const char* to char* */
char *str_copy(const char *orig) {
    char *res = new char[strlen(orig) + 1];
    strcpy(res, orig);
    return res;
}

/* Timestamp */
uint64_t timespec_to_ns(struct timespec t_spec) {
    return t_spec.tv_sec * (uint64_t)1000000000 + t_spec.tv_nsec;
}

struct __attribute((packed)) rdma_buffer_attr {
    uint64_t address;
    uint32_t length;
    union stag {
        /* if we send, we call it local stags */
        uint32_t local_stag;
        /* if we receive, we call it remote stag */
        uint32_t remote_stag;
    } stag;
};

/* Code acknowledgment: rping.c from librdmacm/examples */
int get_addr(const char *dst, struct sockaddr *addr) {
    struct addrinfo *res;
    int ret = -1;
    ret = getaddrinfo(dst, NULL, NULL, &res);
    if (ret) {
        rdma_error("getaddrinfo failed - invalid hostname or IP address\n");
        return ret;
    }
    memcpy(addr, res->ai_addr, sizeof(struct sockaddr_in));
    freeaddrinfo(res);
    return ret;
}

/* Interrupt Exception */
class InterruptException : public std::exception {
   public:
    InterruptException(int s) : S(s) {}
    int S;
};
void sig_to_exception(int s) {
    throw InterruptException(s);
}

/* RDMA codes */
int process_rdma_cm_event(struct rdma_event_channel *echannel,
                          enum rdma_cm_event_type expected_event,
                          struct rdma_cm_event **cm_event) {
    int ret = -1;
    ret = rdma_get_cm_event(echannel, cm_event);
    if (ret) {
        rdma_error("Failed to retrieve a cm event, errno: %d \n", -errno);
        return -errno;
    }
    /* lets see, if it was a good event */
    if (0 != (*cm_event)->status) {
        rdma_error("CM event has non zero status: %d\n", (*cm_event)->status);
        ret = -((*cm_event)->status);
        rdma_ack_cm_event(*cm_event); /* important, we acknowledge the event */
        return ret;
    }
    /* if it was a good event, was it of the expected type */
    if ((*cm_event)->event != expected_event) {
        rdma_error("Unexpected event received: %s [ expecting: %s ]",
                   rdma_event_str((*cm_event)->event),
                   rdma_event_str(expected_event));
        rdma_ack_cm_event(*cm_event); /* important, we acknowledge the event */
        return -1;                    // unexpected event :(
    }
    debug("A new %s type event is received \n", rdma_event_str((*cm_event)->event));
    /* The caller must acknowledge the event */
    return ret;
}

int process_work_completion_events(struct ibv_comp_channel *comp_channel,
                                   struct ibv_wc *wc,
                                   int max_wc,
                                   struct timespec *finish_ts) {
    struct ibv_cq *cq_ptr = NULL;
    void *context = NULL;
    int ret, i, total_wc;

    /* We wait for the notification on the CQ channel */
    ret = ibv_get_cq_event(comp_channel, /* IO channel where we are expecting the notification */
                           &cq_ptr,      /* which CQ has an activity. This should be the same as CQ we created before */
                           &context);    /* Associated CQ user context, which we did set */
    if (ret) {
        rdma_error("Failed to get next CQ event due to %d \n", -errno);
        return -errno;
    }
    /* Request for more notifications. */
    ret = ibv_req_notify_cq(cq_ptr, 0);
    if (ret) {
        rdma_error("Failed to request further notifications %d \n", -errno);
        return -errno;
    }

    /* We got notification. We reap the work completion (WC) element. It is
     * unlikely but a good practice it write the CQ polling code that
     * can handle zero WCs. ibv_poll_cq can return zero. Same logic as
     * MUTEX conditional variables in pthread programming.
     */
    total_wc = 0;
    do {
        ret = ibv_poll_cq(cq_ptr /* the CQ, we got notification for */,
                          max_wc - total_wc /* number of remaining WC elements*/,
                          wc + total_wc /* where to store */);
        if (ret < 0) {
            rdma_error("Failed to poll cq for wc due to %d \n", ret);
            /* ret is errno here */
            return ret;
        }
        total_wc += ret;
    } while (total_wc < max_wc);

    /** TIME: at this point, Last ACK may arrive after rdma operations */
    clock_gettime(CLOCK_REALTIME, finish_ts);
    debug("%d WC are completed \n", total_wc);

    /* Now we check validity and status of I/O work completions */
    for (i = 0; i < total_wc; i++) {
        if (wc[i].status != IBV_WC_SUCCESS) {
            rdma_error("Work completion (WC) has error status: %s at index %d",
                       ibv_wc_status_str(wc[i].status), i);
            /* return negative value */
            return -(wc[i].status);
        }
        // else {
        //     debug("BYTES TRANSFERRED TO SERVER: %d\n", wc[i].byte_len);
        // }
    }

    /* Similar to connection management events, we need to acknowledge CQ events */
    ibv_ack_cq_events(cq_ptr,
                      1 /* we received one event notification. This is not
                      number of WC elements */
    );
    return total_wc;
}

struct ibv_mr *rdma_buffer_register(struct ibv_pd *pd,
                                    void *addr, uint32_t length,
                                    enum ibv_access_flags permission) {
    struct ibv_mr *mr = NULL;
    if (!pd) {
        rdma_error("Protection domain is NULL, ignoring \n");
        return NULL;
    }
    mr = ibv_reg_mr(pd, addr, length, permission);
    if (!mr) {
        rdma_error("Failed to create mr on buffer, errno: %d \n", -errno);
        return NULL;
    }
    debug("Registered: %p , len: %u , stag: 0x%x \n", mr->addr, (unsigned int)mr->length, mr->lkey);
    return mr;
}

struct ibv_mr *rdma_buffer_alloc(struct ibv_pd *pd, uint32_t size,
                                 enum ibv_access_flags permission) {
    struct ibv_mr *mr = NULL;
    if (!pd) {
        rdma_error("Protection domain is NULL \n");
        return NULL;
    }
    void *buf = calloc(1, size);
    if (!buf) {
        rdma_error("failed to allocate buffer, -ENOMEM\n");
        return NULL;
    }
    debug("Buffer allocated: %p , len: %u \n", buf, size);
    mr = rdma_buffer_register(pd, buf, size, permission);
    if (!mr) {
        free(buf);
    }
    return mr;
}

void rdma_buffer_deregister(struct ibv_mr *mr) {
    if (!mr) {
        rdma_error("Passed memory region is NULL, ignoring\n");
        return;
    }
    debug("Deregistered: %p , len: %u , stag : 0x%x \n",
          mr->addr,
          (unsigned int)mr->length,
          mr->lkey);
    ibv_dereg_mr(mr);
}

void rdma_buffer_free(struct ibv_mr *mr) {
    if (!mr) {
        rdma_error("Passed memory region is NULL, ignoring\n");
        return;
    }
    void *to_free = mr->addr;
    rdma_buffer_deregister(mr);
    debug("Buffer %p free'ed\n", to_free);
    free(to_free);
}

class ServerRDMA {
   private:
    /** RDMA connection related resources */
    struct ibv_comp_channel *io_completion_channel = NULL;  // completion channel
    struct rdma_cm_id *cm_server_id = NULL;                 // connection identifier
    struct rdma_cm_id *cm_client_id = NULL;                 // connection identifier
    struct rdma_cm_event *cm_event = NULL;                  // event
    struct ibv_pd *pd = NULL;                               // protection domain
    struct rdma_event_channel *cm_event_channel;            // event-listen channel
    struct ibv_cq *server_cq = NULL;                        // completion queue
    struct ibv_qp_init_attr qp_init_attr;                   // QP attributes
    struct ibv_qp *client_qp;                               // client QP

    /** memory buffer related resources */
    struct ibv_mr *client_metadata_mr = NULL,
                  *server_metadata_mr = NULL,
                  *server_buffer_mr = NULL;
    struct rdma_buffer_attr client_metadata_attr, server_metadata_attr;
    struct ibv_recv_wr client_recv_wr, *bad_client_recv_wr = NULL;
    struct ibv_send_wr server_send_wr, *bad_server_send_wr = NULL;
    struct ibv_sge client_recv_sge, server_send_sge;

   public:
    ServerRDMA() {}

    /* Starts RDMA server by allocating basic connection resources */
    bool start(const char *server_ip, const char *server_port) {
        int ret = -1;
        struct sockaddr_in server_addr;
        bzero(&server_addr, sizeof(server_addr));
        server_addr.sin_family = AF_INET;                /* standard IP NET address */
        server_addr.sin_addr.s_addr = htonl(INADDR_ANY); /* passed address */

        /* Craft server address info */
        ret = get_addr(server_ip, (struct sockaddr *)&server_addr); /* Remember, this will overwrite the port info */
        if (ret) {
            rdma_error("Invalid IP: %s\n", server_ip);
            return false;
        }
        server_addr.sin_port = htons(strtol(server_port, NULL, 0));

        /**-----------------------------------------------------------------*
         *             (1) Allocating basic connection resources            *
         * -----------------------------------------------------------------*/

        /* Open a channel used to report asynchronous communication event */
        cm_event_channel = rdma_create_event_channel();
        if (!cm_event_channel) {
            rdma_error("Creating cm event channel failed with errno : (%d)", -errno);
            return false;
        }
        debug("RDMA CM event channel is created successfully at %p \n", cm_event_channel);

        /* rdma_cm_id is the connection identifier (like socket) which is used
         * to define an RDMA connection.
         */
        ret = rdma_create_id(cm_event_channel, &cm_server_id, NULL, RDMA_PS_TCP);
        if (ret) {
            rdma_error("Creating server cm id failed with errno: %d ", -errno);
            return false;
        }
        debug("A RDMA connection id for the server is created \n");

        /* Explicit binding of rdma_cm_id to the socket credentials */
        ret = rdma_bind_addr(cm_server_id, (struct sockaddr *)&server_addr);
        if (ret) {
            rdma_error("Failed to bind server address, errno: %d \n", -errno);
            return false;
        }
        debug("Server RDMA CM id is successfully binded \n");

        /* Now we start to listen on the passed IP and port. However unlike
         * normal TCP listen, this is a non-blocking call. When a new client is
         * connected, a new connection management (CM) event is generated on the
         * RDMA CM event channel from where the listening id was created. Here we
         * have only one channel, so it is easy. */
        ret = rdma_listen(cm_server_id, 8); /* backlog = 8 clients, same as TCP, see man listen*/
        if (ret) {
            rdma_error("rdma_listen failed to listen on server address, errno: %d ", -errno);
            return false;
        }
        rdma_info("Server is listening successfully at: %s , port: %d \n",
                  inet_ntoa(server_addr.sin_addr),
                  ntohs(server_addr.sin_port));

        /* now, we expect a client to connect and generate a RDMA_CM_EVENT_CONNECT_REQUEST
         * We wait (block) on the connection management event channel for
         * the connect event.
         */
        ret = process_rdma_cm_event(cm_event_channel,
                                    RDMA_CM_EVENT_CONNECT_REQUEST,
                                    &cm_event);
        if (ret) {
            rdma_error("Failed to get cm event, ret = %d \n", ret);
            return false;
        }

        /* Much like TCP connection, listening returns a new connection identifier
         * for newly connected client. In the case of RDMA, this is stored in id
         * field. For more details: man rdma_get_cm_event
         */
        cm_client_id = cm_event->id;

        /* now we acknowledge the event. Acknowledging the event free the resources
         * associated with the event structure. Hence any reference to the event
         * must be made before acknowledgment. Like, we have already saved the
         * client id from "id" field before acknowledging the event.
         */
        ret = rdma_ack_cm_event(cm_event);
        if (ret) {
            rdma_error("Failed to acknowledge the cm event errno: %d \n", -errno);
            return false;
        }
        debug("A new RDMA client connection id is stored at %p\n", cm_client_id);
        rdma_info("[Server] 1/3. Client connection is established.\n");

        /**-----------------------------------------------------------------*
         *         (2) Preparing client connection before accepting it      *
         * -----------------------------------------------------------------*/
        /* When we call this function cm_client_id must be set to a valid identifier.
         * This is where, we prepare client connection before we accept it. This
         * mainly involve pre-posting a receive buffer to receive client side
         * RDMA credentials
         */
        if (!cm_client_id) {
            rdma_error("Client id is still NULL \n");
            return false;
        }

        /* We have a valid connection identifier, let's start to allocate
         * resources. We need:
         * 1. Protection Domains (PD)
         * 2. Memory Buffers
         * 3. Completion Queues (CQ)
         * 4. Queue Pair (QP)
         * Protection Domain (PD) is similar to a "process abstraction"
         * in the operating system. All resources are tied to a particular PD.
         * And accessing resourses across PD will result in a protection fault.
         */

        pd = ibv_alloc_pd(cm_client_id->verbs
                          /* verbs defines a verb's provider,
                           * i.e an RDMA device where the incoming
                           * client connection came */
        );
        if (!pd) {
            rdma_error("Failed to allocate a protection domain errno: %d\n", -errno);
            return false;
        }
        debug("A new protection domain is allocated at %p \n", pd);

        /* Now we need a completion channel, were the I/O completion
         * notifications are sent. Remember, this is different from connection
         * management (CM) event notifications.
         * A completion channel is also tied to an RDMA device, hence we will
         * use cm_client_id->verbs.
         */
        io_completion_channel = ibv_create_comp_channel(cm_client_id->verbs);
        if (!io_completion_channel) {
            rdma_error("Failed to create an I/O completion event channel, %d\n", -errno);
            return false;
        }
        debug("An I/O completion event channel is created at %p \n", io_completion_channel);

        /* Now we create a completion queue (CQ) where actual I/O
         * completion metadata is placed. The metadata is packed into a structure
         * called struct ibv_wc (wc = work completion). ibv_wc has detailed
         * information about the work completion. An I/O request in RDMA world
         * is called "work" ;)
         */
        server_cq = ibv_create_cq(cm_client_id->verbs /* which device*/,
                                  CQ_CAPACITY /* maximum capacity*/,
                                  NULL /* user context, not used here */,
                                  io_completion_channel /* which IO completion channel */,
                                  0 /* signaling vector, not used here*/);
        if (!server_cq) {
            rdma_error("Failed to create a completion queue (cq), errno: %d\n", -errno);
            return false;
        }
        debug("Completion queue (CQ) is created at %p with %d elements \n", server_cq, server_cq->cqe);

        /* Ask for the event for all activities in the completion queue*/
        ret = ibv_req_notify_cq(server_cq /* on which CQ */,
                                0 /* 0 = all event type, no filter*/);
        if (ret) {
            rdma_error("Failed to request notifications on CQ errno: %d \n", -errno);
            return false;
        }

        /* Now the last step, set up the queue pair (send, recv) queues and their capacity.
         * The capacity here is define statically but this can be probed from the
         * device. We just use a small number as defined in rdma_common.h */
        bzero(&qp_init_attr, sizeof(qp_init_attr));
        qp_init_attr.cap.max_recv_sge = MAX_SGE; /* Maximum SGE per receive posting */
        qp_init_attr.cap.max_recv_wr = MAX_WR;   /* Maximum receive posting capacity */
        qp_init_attr.cap.max_send_sge = MAX_SGE; /* Maximum SGE per send posting */
        qp_init_attr.cap.max_send_wr = MAX_WR;   /* Maximum send posting capacity */
        qp_init_attr.qp_type = IBV_QPT_RC;       /* QP type, RC = Reliable connection */
        /* We use same completion queue, but one can use different queues */
        qp_init_attr.recv_cq = server_cq; /* Where should I notify for receive completion operations */
        qp_init_attr.send_cq = server_cq; /* Where should I notify for send completion operations */
        /*Lets create a QP */
        ret = rdma_create_qp(cm_client_id /* which connection id */,
                             pd /* which protection domain*/,
                             &qp_init_attr /* Initial attributes */);
        if (ret) {
            rdma_error("Failed to create QP due to errno: %d\n", -errno);
            return false;
        }
        /* Save the reference for handy typing but is not required */
        client_qp = cm_client_id->qp;
        debug("Client QP created at %p\n", client_qp);
        rdma_info("[Server] 2/3. Preparing resource for connection is finished.\n");

        /**-----------------------------------------------------------------*
         *    (3) Establish receive buffer and accept client connection     *
         * -----------------------------------------------------------------*/
        struct rdma_conn_param conn_param;
        if (!cm_client_id || !client_qp) {
            rdma_error("Client resources are not properly setup\n");
            return false;
        }
        /* we prepare the receive buffer in which we will receive the client metadata*/
        client_metadata_mr = rdma_buffer_register(pd /* which protection domain */,
                                                  &client_metadata_attr /* what memory */,
                                                  sizeof(client_metadata_attr) /* what length */,
                                                  (IBV_ACCESS_LOCAL_WRITE) /* access permissions */);
        if (!client_metadata_mr) {
            rdma_error("Failed to register client attr buffer, errno: %d \n", -ENOMEM);
            return false;
        }

        /* We pre-post this receive buffer on the QP. SGE credentials is where we
         * receive the metadata from the client */
        client_recv_sge.addr = (uint64_t)client_metadata_mr->addr;
        client_recv_sge.length = client_metadata_mr->length;
        client_recv_sge.lkey = client_metadata_mr->lkey;
        /* Now we link this SGE to the work request (WR) */
        bzero(&client_recv_wr, sizeof(client_recv_wr));
        client_recv_wr.sg_list = &client_recv_sge;
        client_recv_wr.num_sge = 1;  // only one SGE
        ret = ibv_post_recv(client_qp /* which QP */,
                            &client_recv_wr /* receive work request*/,
                            &bad_client_recv_wr /* error WRs */);
        if (ret) {
            rdma_error("Failed to pre-post the receive buffer, errno: %d \n", ret);
            return false;
        }
        debug("Receive buffer pre-posting is successful \n");

        /* Now we accept the connection. Recall we have not accepted the connection
         * yet because we have to do lots of resource pre-allocation */
        memset(&conn_param, 0, sizeof(conn_param));
        /* this tell how many outstanding requests can we handle */
        conn_param.initiator_depth = INITIATOR_DEPTH; /* For this exercise, we put a small number here */
        /* This tell how many outstanding requests we expect other side to handle */
        conn_param.responder_resources = RESPONDER_RESOURCES; /* For this exercise, we put a small number */
        ret = rdma_accept(cm_client_id, &conn_param);
        if (ret) {
            rdma_error("Failed to accept the connection, errno: %d \n", -errno);
            return false;
        }

        /* We expect an RDMA_CM_EVNET_ESTABLISHED to indicate that the RDMA
         * connection has been established and everything is fine on both, server
         * as well as the client sides.
         */
        debug("Going to wait for : RDMA_CM_EVENT_ESTABLISHED event \n");
        ret = process_rdma_cm_event(cm_event_channel,
                                    RDMA_CM_EVENT_ESTABLISHED,
                                    &cm_event);
        if (ret) {
            rdma_error("Failed to get the cm event, errnp: %d \n", -errno);
            return false;
        }

        /* We acknowledge the event */
        ret = rdma_ack_cm_event(cm_event);
        if (ret) {
            rdma_error("Failed to acknowledge the cm event %d\n", -errno);
            return false;
        }

        /* Just FYI: How to extract connection information */
        struct sockaddr_in remote_sockaddr;  // to extract connection information
        memcpy(&remote_sockaddr /* where to save */,
               rdma_get_peer_addr(cm_client_id) /* gives you remote sockaddr */,
               sizeof(struct sockaddr_in) /* max size */);
        rdma_info("[Server] --> A new connection is accepted from %s \n", inet_ntoa(remote_sockaddr.sin_addr));
        rdma_info("[Server] 3/3. Connection is established.\n");
        return true;
    }
    bool send_server_metadata() {
        struct ibv_wc wc;
        int ret = -1;
        struct timespec dummyts;

        /* Now, we first wait for the client to start the communication by
         * sending the server's metadata info. The server does not use it
         * in our example. We will receive a work completion notification for
         * our pre-posted receive request.
         */
        ret = process_work_completion_events(io_completion_channel, &wc, 1, &dummyts);
        if (ret != 1) {
            rdma_error("Failed to receive , ret = %d \n", ret);
            return false;
        }

        /* if all good, then we should have client's buffer information, lets see */
        rdma_info("[Server] --> Client side buffer information is received...\n");
        if (!(&client_metadata_attr)) {
            rdma_error("Passed attr is NULL\n");
            return false;
        }
        rdma_info("---------------------------------------------------------\n");
        rdma_info("buffer attr, addr: %p , len: %u , stag : 0x%x \n",
                  (void *)client_metadata_attr.address,
                  (unsigned int)client_metadata_attr.length,
                  client_metadata_attr.stag.local_stag);
        rdma_info("---------------------------------------------------------\n");

        /* We need to setup requested memory buffer. This is where the client will
         * do RDMA READs and WRITEs. */
        server_buffer_mr = NULL;
        if (!pd) {
            rdma_error("Protection domain is NULL \n");
            return false;
        }
        void *buf = calloc(1, client_metadata_attr.length);
        if (!buf) { /* what size to allocate */
            rdma_error("failed to allocate buffer, -ENOMEM\n");
            return false;
        }
        enum ibv_access_flags permission = static_cast<ibv_access_flags>(IBV_ACCESS_LOCAL_WRITE |
                                                                         IBV_ACCESS_REMOTE_READ |
                                                                         IBV_ACCESS_REMOTE_WRITE);
        rdma_info("[Server] Permission: %d \n", permission);
        server_buffer_mr = rdma_buffer_register(pd, /* which protection domain */
                                                buf /* buffer */,
                                                client_metadata_attr.length /* what size to allocate */,
                                                permission /* access permissions */);
        if (!server_buffer_mr) {
            free(buf);
            rdma_error("Server failed to create a buffer, errno: %d \n", -ENOMEM);
            return false;
        }

        /* This buffer is used to transmit information about the above
         * buffer to the client. So this contains the metadata about the server
         * buffer. Hence this is called metadata buffer. Since this is already
         * on allocated, we just register it.
         * We need to prepare a send I/O operation that will tell the
         * client the address of the server buffer.
         */
        server_metadata_attr.address = (uint64_t)server_buffer_mr->addr;
        server_metadata_attr.length = (uint32_t)server_buffer_mr->length;
        server_metadata_attr.stag.local_stag = (uint32_t)server_buffer_mr->lkey;
        server_metadata_mr = rdma_buffer_register(pd /* which protection domain*/,
                                                  &server_metadata_attr /* which memory to register */,
                                                  sizeof(server_metadata_attr) /* what is the size of memory */,
                                                  IBV_ACCESS_LOCAL_WRITE /* what access permission */);
        if (!server_metadata_mr) {
            rdma_error("Server failed to create to hold server metadata, errno: %d \n", -ENOMEM);
            /* we assume that this is due to out of memory error */
            return false;
        }

        /* We need to transmit this buffer. So we create a send request.
         * A send request consists of multiple SGE elements. In our case, we only
         * have one
         */
        server_send_sge.addr = (uint64_t)&server_metadata_attr;
        server_send_sge.length = sizeof(server_metadata_attr);
        server_send_sge.lkey = server_metadata_mr->lkey;
        /* now we link this sge to the send request */
        bzero(&server_send_wr, sizeof(server_send_wr));
        server_send_wr.sg_list = &server_send_sge;
        server_send_wr.num_sge = 1;                     // only 1 SGE element in the array
        server_send_wr.opcode = IBV_WR_SEND;            // This is a send request
        server_send_wr.send_flags = IBV_SEND_SIGNALED;  // We want to get notification
        /* This is a fast data path operation. Posting an I/O request */
        ret = ibv_post_send(client_qp /* which QP */,
                            &server_send_wr /* Send request that we prepared before */,
                            &bad_server_send_wr /* In case of error, this will contain failed requests */);
        if (ret) {
            rdma_error("Posting of server metdata failed, errno: %d \n", -errno);
            return false;
        }
        /* We check for completion notification */
        ret = process_work_completion_events(io_completion_channel, &wc, 1, &dummyts);
        if (ret != 1) {
            rdma_error("Failed to send server metadata, ret = %d \n", ret);
            return false;
        }
        debug("Local buffer metadata has been sent to the client \n");
        rdma_info("[Server] Server sending server-side metadata is finished\n");
        return true;
    }

    bool disconnect_and_cleanup() {
        cm_event = NULL;
        int ret = -1;
        /* Now we wait for the client to send us disconnect event */
        debug("Waiting for cm event: RDMA_CM_EVENT_DISCONNECTED\n");
        ret = process_rdma_cm_event(cm_event_channel,
                                    RDMA_CM_EVENT_DISCONNECTED,
                                    &cm_event);
        if (ret) {
            rdma_error("Failed to get disconnect event, ret = %d \n", ret);
            return false;
        }
        /* We acknowledge the event */
        ret = rdma_ack_cm_event(cm_event);
        if (ret) {
            rdma_error("Failed to acknowledge the cm event %d\n", -errno);
            return false;
        }
        rdma_info("[Server] A disconnect event is received from the client...\n");

        /* We free all the resources */
        /* Destroy QP */
        rdma_destroy_qp(cm_client_id);
        /* Destroy client cm id */
        ret = rdma_destroy_id(cm_client_id);
        if (ret) {
            rdma_error("Failed to destroy client id cleanly, %d \n", -errno);
            // we continue anyways;
        }
        /* Destroy CQ */
        ret = ibv_destroy_cq(server_cq);
        if (ret) {
            rdma_error("Failed to destroy completion queue cleanly, %d \n", -errno);
            // we continue anyways;
        }
        /* Destroy completion channel */
        ret = ibv_destroy_comp_channel(io_completion_channel);
        if (ret) {
            rdma_error("Failed to destroy completion channel cleanly, %d \n", -errno);
            // we continue anyways;
        }
        /* Destroy memory buffers */
        rdma_buffer_free(server_buffer_mr);
        rdma_buffer_deregister(server_metadata_mr);
        rdma_buffer_deregister(client_metadata_mr);
        /* Destroy protection domain */
        ret = ibv_dealloc_pd(pd);
        if (ret) {
            rdma_error("Failed to destroy client protection domain cleanly, %d \n", -errno);
            // we continue anyways;
        }
        /* Destroy rdma server id */
        ret = rdma_destroy_id(cm_server_id);
        if (ret) {
            rdma_error("Failed to destroy server id cleanly, %d \n", -errno);
            // we continue anyways;
        }
        rdma_destroy_event_channel(cm_event_channel);
        rdma_info("[Server] Server shut-down is complete \n");
        return true;
    }

    ~ServerRDMA() {}
};

class ClientRDMA {
   private:
    /** RDMA connection related resources */
    struct sockaddr_in server_addr;                         // server info for next connections
    struct ibv_comp_channel *io_completion_channel = NULL;  // completion channel
    struct rdma_cm_id *cm_server_id = NULL;                 // connection identifier
    struct rdma_cm_id *cm_client_id = NULL;                 // connection identifier
    struct rdma_cm_event *cm_event = NULL;                  // event
    struct ibv_pd *pd = NULL;                               // protection domain
    struct rdma_event_channel *cm_event_channel = NULL;     // event-listen channel
    struct ibv_cq *client_cq = NULL;                        // completion queue
    struct ibv_qp_init_attr qp_init_attr;                   // QP attributes
    struct ibv_qp *client_qp;                               // client QP

    /** memory buffer related resources */
    struct ibv_mr *client_metadata_mr = NULL,
                  *server_metadata_mr = NULL,
                  *client_src_mr = NULL,
                  *client_dst_mr = NULL;
    struct rdma_buffer_attr client_metadata_attr, server_metadata_attr;
    struct ibv_send_wr client_send_wr, *bad_client_send_wr = NULL;
    struct ibv_recv_wr server_recv_wr, *bad_server_recv_wr = NULL;
    struct ibv_sge client_send_sge, server_recv_sge;
    char *src = NULL, *dst = NULL;
    struct timespec ts_start, ts_finish;  // for time measurement
    uint64_t ts_wall_clock; // start of experiment

    // monitoring
    std::vector<std::vector<uint64_t> > fct_records;  // for fct measurement (size, op_type, fct)
    uint64_t txBytes = 0;                             // bytes sent

   public:
    ClientRDMA() {}
    bool start(const char *server_ip, const char *server_port) {
        struct timespec dummyts;
        ts_wall_clock = timespec_to_ns(dummyts); // dummy global start

        fct_records.clear();  // clean records
        fct_records.reserve(10000000);
        int ret = -1;
        struct sockaddr_in server_addr;
        bzero(&server_addr, sizeof(server_addr));
        server_addr.sin_family = AF_INET;                /* standard IP NET address */
        server_addr.sin_addr.s_addr = htonl(INADDR_ANY); /* passed address */

        /* Craft server address info */
        ret = get_addr(server_ip, (struct sockaddr *)&server_addr); /* Remember, this will overwrite the port info */
        if (ret) {
            rdma_error("Invalid IP \n");
            return false;
        }
        server_addr.sin_port = htons(strtol(server_port, NULL, 0));

        /**-----------------------------------------------------------------*
         *                  (1) Client preparing connection                 *
         * -----------------------------------------------------------------*/

        /*  Open a channel used to report asynchronous communication event */
        cm_event_channel = rdma_create_event_channel();
        if (!cm_event_channel) {
            rdma_error("Creating cm event channel failed, errno: %d \n", -errno);
            return false;
        }
        debug("RDMA CM event channel is created at : %p \n", cm_event_channel);

        /* rdma_cm_id is the connection identifier (like socket) which is used
         * to define an RDMA connection.
         */
        ret = rdma_create_id(cm_event_channel, &cm_client_id, NULL, RDMA_PS_TCP);
        if (ret) {
            rdma_error("Creating cm id failed with errno: %d \n", -errno);
            return false;
        }

        /* Resolve destination and optional source addresses from IP addresses  to
         * an RDMA address.  If successful, the specified rdma_cm_id will be bound
         * to a local device. */
        ret = rdma_resolve_addr(cm_client_id, NULL, (struct sockaddr *)&server_addr, RESOLVE_TIMEOUT);
        if (ret) {
            rdma_error("Failed to resolve address, errno: %d \n", -errno);
            return false;
        }
        debug("waiting for cm event: RDMA_CM_EVENT_ADDR_RESOLVED\n");

        ret = process_rdma_cm_event(cm_event_channel,
                                    RDMA_CM_EVENT_ADDR_RESOLVED,
                                    &cm_event);
        if (ret) {
            rdma_error("Failed to receive a valid event, ret = %d \n", ret);
            return false;
        }

        /* we ack the event */
        ret = rdma_ack_cm_event(cm_event);
        if (ret) {
            rdma_error("Failed to acknowledge the CM event, errno: %d\n", -errno);
            return false;
        }
        debug("RDMA address is resolved \n");

        /* Resolves an RDMA route to the destination address in order to
         * establish a connection */
        ret = rdma_resolve_route(cm_client_id, RESOLVE_TIMEOUT);
        if (ret) {
            rdma_error("Failed to resolve route, erno: %d \n", -errno);
            return false;
        }
        debug("waiting for cm event: RDMA_CM_EVENT_ROUTE_RESOLVED\n");

        ret = process_rdma_cm_event(cm_event_channel,
                                    RDMA_CM_EVENT_ROUTE_RESOLVED,
                                    &cm_event);
        if (ret) {
            rdma_error("Failed to receive a valid event, ret = %d \n", ret);
            return false;
        }

        /* we ack the event */
        ret = rdma_ack_cm_event(cm_event);
        if (ret) {
            rdma_error("Failed to acknowledge the CM event, errno: %d \n", -errno);
            return false;
        }
        rdma_info("Trying to connect to server at : %s port: %d \n",
                  inet_ntoa(server_addr.sin_addr),
                  ntohs(server_addr.sin_port));

        /* Protection Domain (PD) is similar to a "process abstraction"
         * in the operating system. All resources are tied to a particular PD.
         * And accessing recourses across PD will result in a protection fault.
         */
        pd = ibv_alloc_pd(cm_client_id->verbs);
        if (!pd) {
            rdma_error("Failed to alloc pd, errno: %d \n", -errno);
            return false;
        }
        debug("pd allocated at %p \n", pd);

        /* Now we need a completion channel, were the I/O completion
         * notifications are sent. Remember, this is different from connection
         * management (CM) event notifications.
         * A completion channel is also tied to an RDMA device, hence we will
         * use cm_client_id->verbs.
         */
        io_completion_channel = ibv_create_comp_channel(cm_client_id->verbs);
        if (!io_completion_channel) {
            rdma_error("Failed to create IO completion event channel, errno: %d\n", -errno);
            return false;
        }
        debug("completion event channel created at : %p \n", io_completion_channel);

        /* Now we create a completion queue (CQ) where actual I/O
         * completion metadata is placed. The metadata is packed into a structure
         * called struct ibv_wc (wc = work completion). ibv_wc has detailed
         * information about the work completion. An I/O request in RDMA world
         * is called "work" ;)
         */
        client_cq = ibv_create_cq(cm_client_id->verbs /* which device*/,
                                  CQ_CAPACITY /* maximum capacity*/,
                                  NULL /* user context, not used here */,
                                  io_completion_channel /* which IO completion channel */,
                                  0 /* signaling vector, not used here*/);
        if (!client_cq) {
            rdma_error("Failed to create CQ, errno: %d \n", -errno);
            return false;
        }
        debug("CQ created at %p with %d elements \n", client_cq, client_cq->cqe);

        /** Request completion notification on a CQ. An event will
         * be added to the completion channel associated with the
         * CQ when an entry is added to the CQ. */
        ret = ibv_req_notify_cq(client_cq, 0);
        if (ret) {
            rdma_error("Failed to request notifications, errno: %d\n", -errno);
            return false;
        }

        /* Now the last step, set up the queue pair (send, recv) queues and their capacity.
         * The capacity here is define statically but this can be probed from the
         * device. We just use a small number as defined in rdma_common.h */
        bzero(&qp_init_attr, sizeof qp_init_attr);
        qp_init_attr.cap.max_recv_sge = MAX_SGE; /* Maximum SGE per receive posting */
        qp_init_attr.cap.max_recv_wr = MAX_WR;   /* Maximum receive posting capacity */
        qp_init_attr.cap.max_send_sge = MAX_SGE; /* Maximum SGE per send posting */
        qp_init_attr.cap.max_send_wr = MAX_WR;   /* Maximum send posting capacity */
        qp_init_attr.qp_type = IBV_QPT_RC;       /* QP type, RC = Reliable connection */
        /* We use same completion queue, but one can use different queues */
        qp_init_attr.recv_cq = client_cq; /* Where should I notify for receive completion operations */
        qp_init_attr.send_cq = client_cq; /* Where should I notify for send completion operations */
        /*Lets create a QP */
        ret = rdma_create_qp(cm_client_id /* which connection id */,
                             pd /* which protection domain*/,
                             &qp_init_attr /* Initial attributes */);
        if (ret) {
            rdma_error("Failed to create QP, errno: %d \n", -errno);
            return false;
        }
        client_qp = cm_client_id->qp;
        debug("Client QP created at %p \n", client_qp);
        rdma_info("[Client] 1/3. Preparation is finished.\n");
        /**-----------------------------------------------------------------*
         * (2) Client pre-post receiver buffer before calling rdma_connect()*
         * -----------------------------------------------------------------*/
        server_metadata_mr = rdma_buffer_register(pd,
                                                  &server_metadata_attr,
                                                  sizeof(server_metadata_attr),
                                                  (IBV_ACCESS_LOCAL_WRITE));
        if (!server_metadata_mr) {
            rdma_error("Failed to setup the server metadata mr, errno: %d \n", -ENOMEM);
            return false;
        }
        server_recv_sge.addr = (uint64_t)server_metadata_mr->addr;
        server_recv_sge.length = (uint32_t)server_metadata_mr->length;
        server_recv_sge.lkey = (uint32_t)server_metadata_mr->lkey;

        /* now we link it to the request */
        bzero(&server_recv_wr, sizeof(server_recv_wr));
        server_recv_wr.sg_list = &server_recv_sge;
        server_recv_wr.num_sge = NUM_SGE;
        ret = ibv_post_recv(client_qp /* which QP */,
                            &server_recv_wr /* receive work request*/,
                            &bad_server_recv_wr /* error WRs */);
        if (ret) {
            rdma_error("Failed to pre-post the receive buffer, errno: %d \n", ret);
            return false;
        }
        debug("Receive buffer pre-posting is successful \n");
        rdma_info("[Client] 2/3. Pre-posting receiver buffer is finished.\n");
        /**-----------------------------------------------------------------*
         * (3)                Client connecting to Server                   *
         * -----------------------------------------------------------------*/
        struct rdma_conn_param conn_param;
        bzero(&conn_param, sizeof(conn_param));
        /* this tell how many outstanding requests can we handle */
        conn_param.initiator_depth = INITIATOR_DEPTH;
        /* This tell how many outstanding requests we expect other side to handle */
        conn_param.responder_resources = RESPONDER_RESOURCES;
        conn_param.retry_count = RETRY_COUNT;  // if fail, then how many times to retry

        /* make connection to server */
        ret = rdma_connect(cm_client_id, &conn_param);
        if (ret) {
            rdma_error("Failed to connect to remote host , errno: %d\n", -errno);
            return false;
        }

        debug("Now, waiting for cm event: RDMA_CM_EVENT_ESTABLISHED\n");
        ret = process_rdma_cm_event(cm_event_channel,
                                    RDMA_CM_EVENT_ESTABLISHED,
                                    &cm_event);
        if (ret) {
            rdma_error("Failed to get cm event, ret = %d \n", ret);
            return false;
        }
        ret = rdma_ack_cm_event(cm_event);
        if (ret) {
            rdma_error("Failed to acknowledge cm event, errno: %d\n",
                       -errno);
            return false;
        }
        rdma_info("[Client] --> The client is connected successfully \n");
        rdma_info("[Client] 3/3. Connection to server is established successfully.\n");

        src = (char *)calloc(MAX_DATA_LEN, 1);
        if (!src) {
            rdma_error("Failed to allocate memory : -ENOMEM\n");
            return false;
        }
        dst = (char *)calloc(MAX_DATA_LEN, 1);
        if (!dst) {
            rdma_error("Failed to allocate destination memory, -ENOMEM\n");
            free(src);
            return false;
        }
        rdma_info("[Client] Maximum datalen available to transfer: %u Bytes\n", MAX_DATA_LEN);
        return true;
    }

    bool send_client_metadata() {
        struct ibv_wc wc[2];
        int ret = -1;
        struct timespec dummyts;

        enum ibv_access_flags permission = static_cast<ibv_access_flags>(IBV_ACCESS_LOCAL_WRITE |
                                                                         IBV_ACCESS_REMOTE_READ |
                                                                         IBV_ACCESS_REMOTE_WRITE);
        rdma_info("[Client] Permission: %d \n", permission);
        rdma_info("[Client] local buffer's maximum datalen: %u \n", MAX_DATA_LEN);
        client_src_mr = rdma_buffer_register(pd /* protection domain */,
                                             src,          /* local buffer */
                                             MAX_DATA_LEN, /* data len */
                                             permission /* permission to memory */);
        if (!client_src_mr) {
            rdma_error("Failed to register the first buffer, ret = %d \n", ret);
            return false;
        }

        rdma_info("[Client] remote buffer's maximum datalen: %u \n", MAX_DATA_LEN);
        client_dst_mr = rdma_buffer_register(pd /* protection domain */,
                                             dst /* remote memory buffer to access */,
                                             MAX_DATA_LEN /* datalen to transfer */,
                                             permission /* permission to access the buffer */);
        if (!client_dst_mr) {
            rdma_error("We failed to create the destination buffer, errno: %d \n", -ENOMEM);
            return false;
        }

        /* we prepare metadata for the first buffer */
        client_metadata_attr.address = (uint64_t)client_src_mr->addr;
        client_metadata_attr.length = client_src_mr->length;
        client_metadata_attr.stag.local_stag = client_src_mr->lkey;
        /* now we register the metadata memory */
        client_metadata_mr = rdma_buffer_register(pd,
                                                  &client_metadata_attr,
                                                  sizeof(client_metadata_attr),
                                                  IBV_ACCESS_LOCAL_WRITE);
        if (!client_metadata_mr) {
            rdma_error("Failed to register the client metadata buffer, ret = %d \n", ret);
            return false;
        }

        /* now we fill up SGE */
        client_send_sge.addr = (uint64_t)client_metadata_mr->addr;
        client_send_sge.length = (uint32_t)client_metadata_mr->length;
        client_send_sge.lkey = client_metadata_mr->lkey;

        /* now we link to the send work request */
        bzero(&client_send_wr, sizeof(client_send_wr));
        client_send_wr.sg_list = &client_send_sge;
        client_send_wr.num_sge = 1;
        client_send_wr.opcode = IBV_WR_SEND;
        client_send_wr.send_flags = IBV_SEND_SIGNALED;

        /* Now we post it */
        ret = ibv_post_send(client_qp,
                            &client_send_wr,
                            &bad_client_send_wr);  // refer to verbsEP.hpp
        if (ret) {
            rdma_error("Failed to send client metadata, errno: %d \n", -errno);
            return false;
        }
        /* at this point we are expecting 2 work completion. One for our
         * send and one for recv that we will get from the server for
         * its buffer information */
        ret = process_work_completion_events(io_completion_channel, wc, 2, &dummyts);
        if (ret != 2) {
            rdma_error("We failed to get 2 work completions , ret = %d \n", ret);
            return false;
        }
        debug("Server sent us its buffer location and credentials, showing \n");
        if (!(&server_metadata_attr)) {
            rdma_error("Passed attr is NULL\n");
            return false;
        }
        rdma_info("---------------------------------------------------------\n");
        rdma_info("buffer attr, addr: %p , len: %u , stag : 0x%x \n",
                  (void *)server_metadata_attr.address,
                  (unsigned int)server_metadata_attr.length,
                  server_metadata_attr.stag.local_stag);
        rdma_info("---------------------------------------------------------\n");
        rdma_info("[Client] Client exchanging buffer metadata with Server is finished\n");
        return true;
    }

    bool remote_memory_ops(const ibv_wr_opcode op_type, const uint32_t &datalen) {
        /* This function does :
         * 1) Prepare memory buffers for RDMA operations
         * 2) RDMA write from src -> remote buffer (op_type == IBV_ACCESS_REMOTE_WRITE)
         * 3) or, RDMA read from remote bufer -> dst (op_type == IBV_ACCESS_REMOTE_READ)
         */
        struct ibv_wc wc;
        int ret = -1;

        uint32_t qp_num = client_qp->qp_num;
        if (op_type == IBV_WR_RDMA_WRITE) {
            /* Copy the local buffer into the remote buffer. We will reuse the previous variables. */
            /* now we fill up SGE */
            client_send_sge.addr = (uint64_t)client_src_mr->addr;
            client_send_sge.length = datalen;  // (uint32_t)client_src_mr->length;
            client_send_sge.lkey = client_src_mr->lkey;

        } else if (op_type == IBV_WR_RDMA_READ) {
            /* Step 2: we prepare a READ using same variables but for destination */
            client_send_sge.addr = (uint64_t)client_dst_mr->addr;
            client_send_sge.length = datalen;  // (uint32_t)client_dst_mr->length;
            client_send_sge.lkey = client_dst_mr->lkey;

        } else {
            rdma_info("[Client] Supported Ops: IBV_WR_RDMA_WRITE/ IBV_WR_RDMA_READ/ \n");
            return false;
        }

        /* now we link to the send work request */
        bzero(&client_send_wr, sizeof(client_send_wr));
        client_send_wr.sg_list = &client_send_sge;
        client_send_wr.num_sge = 1;
        client_send_wr.opcode = op_type;
        client_send_wr.send_flags = IBV_SEND_SIGNALED;

        /* we have to tell server side info for RDMA */
        client_send_wr.wr.rdma.rkey = server_metadata_attr.stag.remote_stag;
        client_send_wr.wr.rdma.remote_addr = server_metadata_attr.address;

        /* Now we post it */
        clock_gettime(CLOCK_REALTIME, &ts_start);  // start point
        ret = ibv_post_send(client_qp,
                            &client_send_wr,
                            &bad_client_send_wr);
        if (ret) {
            rdma_error("Failed to write (read) client's dst (src) buffer, errno: %d \n", -errno);
            return false;
        }

        /* at this point we are expecting 1 work completion for the write/read */
        ret = process_work_completion_events(io_completion_channel,
                                             &wc,
                                             1,
                                             &ts_finish);
        if (ret != 1) {
            rdma_error("We failed to get 1 work completions , ret = %d \n", ret);
            return false;
        }

        uint64_t ts_start_ns = timespec_to_ns(ts_start);
        uint64_t ts_finish_ns = timespec_to_ns(ts_finish);
        fct_records.push_back({(uint64_t)datalen,
                               (uint64_t)op_type,
                               (uint64_t)qp_num,
                               ts_finish_ns - ts_start_ns, // elapsed time
                               ts_start_ns - ts_wall_clock // start time
                               });
        txBytes += datalen;
        rdma_info("[Client] Client side Op is complete (size: %lu, op_type: %lu, qp_num: %lu, fct: %lu, start: %lu) \n",
                  (uint64_t)datalen, (uint64_t)op_type, (uint64_t)qp_num, ts_finish_ns - ts_start_ns, ts_start_ns - ts_wall_clock);

        // // for protego debugging
        // if (ts_finish_ns - ts_start_ns > 5000000) {
        //     printf("Maybe timeout? %lu\n", ts_finish_ns - ts_start_ns);
        //     return false;
        // }

        return true;
    }

    bool disconnect_and_cleanup() {
        cm_event = NULL;
        int ret = -1;
        /* active disconnect from the client side */
        ret = rdma_disconnect(cm_client_id);
        if (ret) {
            rdma_error("Failed to disconnect, errno: %d \n", -errno);
            // continuing anyways
        }
        ret = process_rdma_cm_event(cm_event_channel,
                                    RDMA_CM_EVENT_DISCONNECTED,
                                    &cm_event);
        if (ret) {
            rdma_error("Failed to get RDMA_CM_EVENT_DISCONNECTED event, ret = %d\n", ret);
            // continuing anyways
        }
        ret = rdma_ack_cm_event(cm_event);
        if (ret) {
            rdma_error("Failed to acknowledge cm event, errno: %d\n", -errno);
            // continuing anyways
        }
        /* Destroy QP */
        rdma_destroy_qp(cm_client_id);
        /* Destroy client cm id */
        ret = rdma_destroy_id(cm_client_id);
        if (ret) {
            rdma_error("Failed to destroy client id cleanly, %d \n", -errno);
            // we continue anyways;
        }
        /* Destroy CQ */
        ret = ibv_destroy_cq(client_cq);
        if (ret) {
            rdma_error("Failed to destroy completion queue cleanly, %d \n", -errno);
            // we continue anyways;
        }
        /* Destroy completion channel */
        ret = ibv_destroy_comp_channel(io_completion_channel);
        if (ret) {
            rdma_error("Failed to destroy completion channel cleanly, %d \n", -errno);
            // we continue anyways;
        }
        /* Destroy memory buffers */
        rdma_buffer_deregister(server_metadata_mr);
        rdma_buffer_deregister(client_metadata_mr);
        rdma_buffer_deregister(client_src_mr);
        rdma_buffer_deregister(client_dst_mr);
        /* We free the buffers */
        free(src);
        free(dst);
        /* Destroy protection domain */
        ret = ibv_dealloc_pd(pd);
        if (ret) {
            rdma_error("Failed to destroy client protection domain cleanly, %d \n", -errno);
            // we continue anyways;
        }
        rdma_destroy_event_channel(cm_event_channel);
        rdma_info("[Client] Client disconnect and resource clean-up is complete \n");
        return true;
    }

    uint64_t flush_fct_records(FILE *fout) {
        uint64_t n_records = fct_records.size();
        fprintf(fout, "datalen,fct\n");
        for (auto arr : fct_records) {
            fprintf(fout, "%lu,%lu\n", arr[0], arr[3]);
            // datalen, op_type (0:WR, ...), qp_num, fct, ts_start
            // fprintf(fout, "%lu,%lu,%lu,%lu,%lu\n", arr[0], arr[1], arr[2], arr[3], arr[4]);
        }
        // fprintf(fout, "%lu\n", txBytes);
        fflush(fout);
        clear_fct_records();
        return n_records;
    }

    void clear_fct_records() {
        fct_records.clear();
        fct_records.reserve(10000000);
        txBytes = 0;
        rdma_info("[Client] clear up fct history and statistics\n");
    }

    void set_wall_clock(uint64_t wall_clock = 0) {
        ts_wall_clock = wall_clock; // for reference
    }

    ~ClientRDMA() {}
};

}  // namespace rdma_simple