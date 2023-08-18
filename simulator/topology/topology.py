import enum
import sys
import typing
import copy
import heapq
import math
import random
import networkx as nx
import matplotlib.pyplot as plt
from progress.spinner import Spinner

sys.path.append("../")
from utils.lg_logging import *

MAX_NUMBER_OF_SWITCHES = 100000 # 100k
MAX_NUMBER_OF_LINKS = 1000000 # 1M
DEFAULT_IS_LG_LINK = True
INITIAL_LINK_LOSS_RATE = 1e-18
MAX_PORTS_PER_PIPE = 16

POD_SHUFFLE_RAND_SEED = 5469321578 # for reproducible results with same trace + sol
partial_deploy_rand_gen = random.Random(POD_SHUFFLE_RAND_SEED)

class TopoType(enum.Enum):
    FatTree   = 1
    LeafSpine = 2
    FbFabric  = 3

topotype_to_tiers = {
    TopoType.FatTree: 3,
    TopoType.LeafSpine: 2,
    TopoType.FbFabric: 3
}

class SwitchType(enum.Enum):
    # Note: the numbering matters
    # lower numbers are downstream
    # higher numbers are upstream
    ALL   = 0
    TOR   = 1
    AGG   = 2
    CORE  = 3
    LEAF  = 4
    SPINE = 5

class PodCapacityType(enum.Enum):
    ToR_to_Agg = enum.auto()
    Agg_to_Core = enum.auto()

linktype_to_pod_capacitytype = {
    LinkType.TOR_AGG: PodCapacityType.ToR_to_Agg,
    LinkType.AGG_CORE: PodCapacityType.Agg_to_Core
}

TOPO_REQUIRED_PARAMS = {
    TopoType.FatTree: ['k', 'link_capacity'],
    TopoType.LeafSpine: ['num_leaf', 'num_spine', 'link_capacity'],
    TopoType.FbFabric: ['num_pods', 'oversubscription', 'link_capacity', 'tors_per_pod']
}

fbTopo_switchType_to_num_pipes = {
    SwitchType.TOR: 2,
    SwitchType.AGG: 6
    # SwitchType.CORE: 
    # num_links = num_pods
    # int(num_links/16) + 1 (if num_links%16 != 0)
}

def switch_id_generator(max_number_of_switches):
    for id in range(max_number_of_switches):
        yield(id)

def link_id_generator(max_number_of_links):
    for id in range(max_number_of_links):
        yield(id)

TOPO_BUILDER_FUNCS = {}  # empty for now. Filled after func defs

class Topology(object):
    def add_switch_to_typewise_list(self, switch_id, switch_type):
        """ 
        Helper function to maintain list of switches per switch type
        """
        if switch_type not in self.switch_typewise_list:
            self.switch_typewise_list[switch_type] = [switch_id]
        else:
            self.switch_typewise_list[switch_type].append(switch_id)

    def __init__(self, topo_type: TopoType, sim_logger: SimulationLogger = None) -> None:
        """ 
        Default constructor. Constructs an empty topo of the specified type.

        Arguments: 
            topo_type: enum. Type of topology
        """
        if topo_type not in TopoType:
            print("Invalid topo_type. Should be one of the enum TopoType:")
            for value in TopoType:
                print(value.name)
            sys.exit(1)
        
        # stores the type of topology. 
        # Determines the topo build function to call.
        self.type = topo_type

        # to (later) store the topo_params dict
        self.topo_params = {}

        # simulation logger instance
        self.sim_logger = sim_logger

        # stored the number of tiers in the topology
        self.tiers = topotype_to_tiers[topo_type]

        # Main networkx Graph object
        self._graph = nx.Graph()

        # Generator function instance to generate switch IDs from 0
        self.global_switch_id = switch_id_generator(MAX_NUMBER_OF_SWITCHES)
        # Generator function instance to generate link IDs from 0
        self.global_link_id = link_id_generator(MAX_NUMBER_OF_LINKS)

        # Dictionary to store list of switch ID lists as per their types
        # Example contents: {SwitchType.CORE: [0, 1, 2]}
        self.switch_typewise_list = {}

        # Dictionary to lookup switch ID pair for a given link ID
        # Need to maintain this since networkx Graph object only allows 
        # looking up an edge (link) by the node (switch) ID pair
        self.linkid_to_switchpair_mapping = {}

        # link ID -> set() of affected ToR IDs mapping
        self.link_id_to_affected_tors = {}

        # link ID -> pod ID dict
        self.link_id_to_pod_id = {}

        # dictionary to keep track of disabled links
        self.disabled_links = set() # set. enables O(1) lookup

        # dictionary to keep track of corrupting links
        self.corrupting_links = set() # set. enables O(1) lookup

        #################
        ###  METRICS  ###
        #################

        # tor ID -> [list of paths to the core]
        self.paths_to_core = {}  # used mainly for debugging
        self.num_paths_to_core = {} # tor_id -> num paths to core
        
        # pod_id -> {PodCapacityType.ToR_to_Agg: X, PodCapacityType.Agg_to_Core: Y}
        self.per_pod_capacity = {} 

        self.num_links = 0
        self.num_tors = 0
        self.num_pods = 0

        self.num_lg_enabled_links = 0

        # global sum of all links' loss rates
        self.total_loss_rate = 0

        # global sum of all links' effective loss rates
        self.total_effective_loss_rate = 0

        # priority queue of top loss rates
        self.top_loss_rates_heap = [INITIAL_LINK_LOSS_RATE]

        # priority queue of top lg_ports_per_pipe
        self.top_lg_ports_per_pipe_heap = [0]
    
    def log(self, msg: str) -> None:
        if self.sim_logger != None:
            self.sim_logger.simulation_log(msg)

    def add_switch(self, switch_type: SwitchType, extra_attr = {}):
        """ 
        Adds new switch to the topology. 
        
        Switch ID is chosen from a global generator.

        Arguments: 
            switch_type : enum SwitchType
            extra_attr  : dict. Extra attributes to attach to the switch
            is_lg_switch: bool. [optional] 
                          Default value is DEFAULT_IS_LG_SWITCH
            
        Return: 
            switch_id: int. switch_id of the added switch
        """
        # get next switch_id
        switch_id = next(self.global_switch_id) 

        # track the switch in our own typewise switch list
        self.add_switch_to_typewise_list(switch_id, switch_type) 

        # determine the correct num_pipes for this switch type for this topo
        if self.type == TopoType.FatTree:
            num_links = self.topo_params['k']
            num_pipes = int(num_links / MAX_PORTS_PER_PIPE)
            if (num_links % MAX_PORTS_PER_PIPE) != 0:
                num_pipes += 1  # for the remaining ports            
        elif self.type == TopoType.FbFabric:
            oversubscription = self.topo_params['oversubscription']
            num_pods = self.topo_params['num_pods']
            tors_per_pod = self.topo_params['tors_per_pod']
            # compute the topo parameters
            core_switches_per_spine_plane = int(tors_per_pod / oversubscription)
            if switch_type == SwitchType.TOR:
                num_pipes = fbTopo_switchType_to_num_pipes[SwitchType.TOR]
                num_links = 4 # each TOR in FbFabric has exactly 4 links                
            elif switch_type == SwitchType.AGG:
                num_pipes = fbTopo_switchType_to_num_pipes[SwitchType.AGG]
                num_links = tors_per_pod + core_switches_per_spine_plane                
            elif switch_type == SwitchType.CORE:
                num_links = self.topo_params['num_pods']
                num_pipes = int(num_links / MAX_PORTS_PER_PIPE)
                if (num_links % MAX_PORTS_PER_PIPE) != 0:
                    num_pipes += 1  # for the remaining ports
        elif self.type == TopoType.LeafSpine:
            print(TERM_ERROR_STR + "num_pipes NOT implemented for LeafSpine topo")
            sys.exit(1)

        ports_per_pipe = int(num_links / num_pipes)
        if num_links % num_pipes != 0:
            ports_per_pipe += 1
        assert ports_per_pipe >= 0, "ports_per_pipe is zero. topoType:{}, switchType:{}, \
             num_links:{}, num_pipes:{}".format(self.type.name, switch_type.name, num_links, num_pipes)

        # prepare the initial lg_ports_per_pipe dict
        lg_ports_per_pipe_dict = {}
        for i in range(num_pipes):
            lg_ports_per_pipe_dict[i] = 0

        # add the switch as an integer node to the internal _graph
        self._graph.add_node(switch_id, type=switch_type, \
                             link_id_list=[], \
                             num_pipes=num_pipes, \
                             num_links=num_links, \
                             ports_per_pipe=ports_per_pipe, \
                             lg_ports_per_pipe = lg_ports_per_pipe_dict, \
                             **extra_attr)

        # return the switch_id. Helps the topo builder function
        return switch_id

    def add_link_to_switch(self, sw_id: int, link_id: int) -> None:
        link_id_list = self.get_switch_attribute_by_ref(sw_id, 'link_id_list')
        link_id_list.append(link_id)
    
    def add_link(self, sw1_id, sw2_id, link_capacity, extra_attr = {}, is_lg_link = DEFAULT_IS_LG_LINK) -> int:
        """ 
        Adds link between two switches with specified link capacity (in Gbps)

        Link ID is chosen from a global generator. Loss rate is set to zero.
        Link attributes: id, capacity, loss_rate

        Arguments:
            sw1_id: integer. ID of the first switch. 
            sw2_id: integer. ID of the second switch.
            capacity: float. Link capacity in Gbps.
        """
        # get next link_id
        link_id = next(self.global_link_id) 

        # count LG-enabled links
        if is_lg_link:
            self.num_lg_enabled_links += 1

        # record the link id -> switch pair mapping
        self.linkid_to_switchpair_mapping[link_id] = (sw1_id, sw2_id)

        # Add the link with the attributed to the internal _graph
        self._graph.add_edge(sw1_id, sw2_id, id=link_id, \
            capacity=link_capacity, effective_capacity=link_capacity, \
            loss_rate=INITIAL_LINK_LOSS_RATE, effective_loss_rate=INITIAL_LINK_LOSS_RATE, \
            disabled=False, lg_capable = is_lg_link, lg_enabled = False, **extra_attr)
        
        # Add the link_id to both the switches
        self.add_link_to_switch(sw1_id, link_id)
        self.add_link_to_switch(sw2_id, link_id)

        return link_id

    def record_link_top_loss_rates(self, link_id, loss_rate):
        if link_id in self.corrupting_links:
            # link is already corrupting and 
            # this is an updated loss rate. 
            # So, remove old_loss_rate first
            old_loss_rate = self.get_link_loss_rate(link_id)
            self.top_loss_rates_heap.remove(old_loss_rate)
            heapq.heapify(self.top_loss_rates_heap)
        # now add the new loss rate
        heapq.heappush(self.top_loss_rates_heap, loss_rate)

    def remove_from_top_loss_rates(self, loss_rate):
        self.top_loss_rates_heap.remove(loss_rate)
        heapq.heapify(self.top_loss_rates_heap)

    def record_top_lg_ports_per_pipe(self, lg_ports_per_pipe):
        heapq.heappush(self.top_lg_ports_per_pipe_heap, lg_ports_per_pipe)

    def remove_top_lg_ports_per_pipe(self, lg_ports_per_pipe):
        self.top_lg_ports_per_pipe_heap.remove(lg_ports_per_pipe)
        heapq.heapify(self.top_lg_ports_per_pipe_heap)

    
    def get_link_attributes_dict(self, link_id):
        """
        Returns the attribute dict for the specified link.

        Arguments:
            link_id: integer. ID of the link.
        """
        # Get the switch pair that the link connects
        switch_pair = self.linkid_to_switchpair_mapping[link_id] 
        sw1_id = switch_pair[0]
        sw2_id = switch_pair[1]
        return self._graph.edges[sw1_id, sw2_id]

    def get_link_attribute(self, link_id, attribute_key):
        """
        Returns the link attribute value for the specified attribute key

        Arguments:
            link_id: integer. ID of the link.
            attribute_key: string. Attribute key.
        """
        # Get the switch pair that the link connects
        switch_pair = self.linkid_to_switchpair_mapping[link_id] 
        sw1_id = switch_pair[0]
        sw2_id = switch_pair[1]
        return self._graph.edges[sw1_id, sw2_id][attribute_key]

    def set_link_attribute(self, link_id, attribute_key, attribute_value):
        """
        Sets the link attribute value for the specified attribute key

        Arguments:
            link_id: integer. ID of the link.
            attribute_key: string. Attribute key.
            attribute_value: type depends on the attribute key
        """
        # Get the switch pair that the link connects
        switch_pair = self.linkid_to_switchpair_mapping[link_id] 
        sw1_id = switch_pair[0]
        sw2_id = switch_pair[1]
        self._graph.edges[sw1_id, sw2_id][attribute_key] = attribute_value

    def get_switch_attributes_dict(self, switch_id):
        """
        Returns the attribute dict for the specified switch.

        Arguments:
            switch_id: integer. ID of the switch.
        """
        return self._graph.nodes[switch_id]

    def get_switch_attribute(self, switch_id: int, attribute: str) -> typing.Any:
        """
        Returns the specified attribute for the specified switch.

        Arguments:
            switch_id: integer. ID of the switch.
            attribute: str. attribute required
        """
        return copy.copy(self.get_switch_attributes_dict(switch_id)[attribute])
    
    def get_switch_attribute_by_ref(self, switch_id: int, attribute: str) -> typing.Any:
        """
        Returns the specified attribute for the specified switch.

        Arguments:
            switch_id: integer. ID of the switch.
            attribute: str. attribute required
        """
        return self.get_switch_attributes_dict(switch_id)[attribute]

    def set_switch_attribute(self, switch_id: int, attribute: str, value: typing.Any) -> None:
        """ 
        """
        self._graph.nodes[switch_id][attribute] = value


    def get_switch_type(self, switch_id: int) -> SwitchType:
        return self.get_switch_attribute(switch_id, "type")

    def get_num_active_uplinks(self, agg_id: int) -> int:
        assert self.get_switch_type(agg_id) == SwitchType.AGG, \
            "only AGG switches maintain num_active_uplinks"
        return self.get_switch_attribute(agg_id, 'num_active_uplinks')

    def get_connected_agg_switches(self, tor_id: int) -> list:
        assert self.get_switch_type(tor_id) == SwitchType.TOR, \
            "only TOR switches maintain the agg switch list"
        return self.get_switch_attribute(tor_id, 'agg_switches')

    def get_internal_graph(self):
        """ 
        Returns the internal _graph object. For debugging only!
        """
        return self._graph

    def add_agg_switch_to_tor(self, tor_id: int, agg_id: int) -> None:
        assert self.get_switch_type(tor_id) == SwitchType.TOR, \
            "can only add to a tor switch"
        assert self.get_switch_type(agg_id) == SwitchType.AGG, \
            "can only add an agg switch"
        
        self._graph.nodes[tor_id]['agg_switches'].append(agg_id)

    def remove_agg_switch_from_tor(self, tor_id: int, agg_id: int) -> None:
        assert self.get_switch_type(tor_id) == SwitchType.TOR, \
            "can only remove from a tor switch"
        assert self.get_switch_type(agg_id) == SwitchType.AGG, \
            "can only remove an agg switch"
        
        try:
            self._graph.nodes[tor_id]['agg_switches'].remove(agg_id)
        except ValueError:
            print(TERM_ERROR_STR + "Failed to remove agg_id {} from tor_id {}".format(agg_id, tor_id))
            # print(self._graph.nodes[tor_id]['agg_switches'])
            raise

    def increment_num_active_uplinks(self, agg_id: int) -> None:
        assert self.get_switch_type(agg_id) == SwitchType.AGG, \
            "only Agg switch maintains num_active_uplinks"
        
        self._graph.nodes[agg_id]['num_active_uplinks'] += 1

    def decrement_num_active_uplinks(self, agg_id: int) -> None:
        assert self.get_switch_type(agg_id) == SwitchType.AGG, \
            "only Agg switch maintains num_active_uplinks"
        self._graph.nodes[agg_id]['num_active_uplinks'] -= 1

    def get_switch_pair_types(self, link_id: int) -> set:
        sw1, sw2 = self.linkid_to_switchpair_mapping[link_id]

        sw1_type = self.get_switch_type(sw1)
        sw2_type = self.get_switch_type(sw2)

        return set([sw1_type, sw2_type])
    
    def get_pipe_id(self, sw_id: int, link_id: int) -> int:
        # CAUTION: getting list by ref is to avoid memcpy for efficiency only
        # DO NOT modify this list_of_links
        list_of_links = self.get_switch_attribute_by_ref(sw_id, 'link_id_list')
        num_pipes = self.get_switch_attribute(sw_id, 'num_pipes')
        link_idx = list_of_links.index(link_id)
        ports_per_pipe = self.get_switch_attribute(sw_id, 'ports_per_pipe')
        pipe_id = link_idx % num_pipes  # INITIAL method
        # pipe_id = int(link_idx / ports_per_pipe) # NEWER method (worse!)
        return pipe_id
    
    def get_lg_ports_per_pipe(self, switch_id: int) -> dict:
        return self.get_switch_attribute_by_ref(switch_id, 'lg_ports_per_pipe')

    def incr_lg_ports_per_pipe(self, switch_id: int, link_id: int) -> int:
        pipe_id = self.get_pipe_id(switch_id, link_id)
        lg_ports_per_pipe = self.get_switch_attribute_by_ref(switch_id, 'lg_ports_per_pipe')
        curr_value = lg_ports_per_pipe[pipe_id]
        new_value = curr_value + 1

        # update the new_value in the switch dict
        lg_ports_per_pipe[pipe_id] = new_value

        self.log("[Incr lg ports] link_id: {}, switch_id: {} [{}], pipe_id: {} => {}".format(link_id, switch_id, self.get_switch_type(switch_id).name, pipe_id, new_value))

        # Do book keeping for tracking the max value 
        if curr_value != 0: # need to remove from the heap
            self.remove_top_lg_ports_per_pipe(curr_value)
        
        self.record_top_lg_ports_per_pipe(new_value)

    def decr_lg_ports_per_pipe(self, switch_id: int, link_id: int) -> int:
        pipe_id = self.get_pipe_id(switch_id, link_id)
        lg_ports_per_pipe = self.get_switch_attribute_by_ref(switch_id, 'lg_ports_per_pipe')
        curr_value = lg_ports_per_pipe[pipe_id]
        new_value = curr_value - 1

        # update the new_value in the switch dict
        lg_ports_per_pipe[pipe_id] = new_value

        self.log("[Decr lg ports] link_id: {}, switch_id: {} [{}], pipe_id: {} => {}".format(link_id, switch_id, self.get_switch_type(switch_id).name, pipe_id, new_value))

        # the new_value should always remain >= 0
        assert new_value >= 0, "lg_ports_per_pipe became negative: switch_id: {}, pipe: {}".format(switch_id, pipe_id)

        self.remove_top_lg_ports_per_pipe(curr_value) # definitely this value is > 0

        if new_value != 0:
            self.record_top_lg_ports_per_pipe(new_value)


    def build(self, topo_params, spinner: Spinner):
        """ 
        Main function that builds the topology.

        Calls the topo builder function based on self.type
        Argument:
            topo_params: dict. Should contain respective topo's params
        """
        TOPO_BUILDER_FUNCS[self.type](self, topo_params, spinner) # call appropriate builder func
        # if self.type == TopoType.FatTree:
        #     build_topo_fattree(self, topo_params)
        # elif self.type == TopoType.LeafSpine:
        #     build_topo_leafspine(self, topo_params)

    def is_link_disabled(self, link_id) -> bool:
        return self.get_link_attribute(link_id, "disabled")

    def get_linkguardian_enabled(self, link_id) -> bool:
        return self.get_link_attribute(link_id, "lg_enabled")

    def set_linkguardian_enabled(self, link_id) -> None:
        already_enabled = self.get_link_attribute(link_id, "lg_enabled")
        self.set_link_attribute(link_id, "lg_enabled", True)

        if not already_enabled: # we are newly enabling LG
            # track the lg_ports_per_pipe for both the switches
            for switch_id in self.linkid_to_switchpair_mapping[link_id]:
                # for loop over the two switches connected by the link
                self.incr_lg_ports_per_pipe(switch_id, link_id)

    def get_linkguardian_capable(self, link_id) -> bool:
        return self.get_link_attribute(link_id, "lg_capable")

    def get_link_type(self, link_id) -> LinkType:
        return self.get_link_attribute(link_id, "link_type")

    def get_link_capacity(self, link_id) -> float:
        return self.get_link_attribute(link_id, "capacity")

    def get_effective_link_capacity(self, link_id) -> float:
        return self.get_link_attribute(link_id, "effective_capacity")

    def get_link_loss_rate(self, link_id: int) -> float:
        return self.get_link_attribute(link_id, "loss_rate")

    def get_link_effective_loss_rate(self, link_id: int) -> float:
        return self.get_link_attribute(link_id, "effective_loss_rate")
    
    def disable_link(self, link_id) -> None:
        loss_rate = self.get_link_loss_rate(link_id)

        self.set_link_attribute(link_id, "disabled", True)
        
        # add the link to the set of disabled links
        self.disabled_links.add(link_id)

        # remove the link from the set of corrupting links
        self.corrupting_links.remove(link_id)

        # remove the link's loss rate from the top loss rates heap
        self.remove_from_top_loss_rates(loss_rate)
        
        # remove the link's loss rate contribution from total loss rate
        self.total_loss_rate -= loss_rate

        # remove the link's effective loss rate contribution from total
        # effective loss rate
        self.total_effective_loss_rate -= self.get_link_effective_loss_rate(link_id)

        # next block first updates the ToR and Agg switch attributes
        # then it re-calculates the paths to core for each affected ToR
        sw1, sw2 = self.linkid_to_switchpair_mapping[link_id]
        sw1_type = self.get_switch_type(sw1)
        sw2_type = self.get_switch_type(sw2)

        switch_pair_types = set([sw1_type, sw2_type])

        if sw1_type == SwitchType.TOR:
            tor_switch = sw1
        elif sw2_type == SwitchType.TOR:
            tor_switch = sw2

        if sw1_type == SwitchType.AGG:
            agg_switch = sw1
        elif sw2_type == SwitchType.AGG:
            agg_switch = sw2

        if sw1_type == SwitchType.CORE:
            core_switch = sw1
        elif sw2_type == SwitchType.CORE:
            core_switch = sw2

        if switch_pair_types == set([SwitchType.TOR, SwitchType.AGG]):
            # it is a ToR-Agg Link
            # For ToR sw: remove the agg switch from the list
            self.remove_agg_switch_from_tor(tor_switch, agg_switch)

        elif switch_pair_types == set([SwitchType.AGG, SwitchType.CORE]):
            # it is a Agg-Core Link
            # For Agg sw: decrement the num_active_uplinks
            self.decrement_num_active_uplinks(agg_switch)

        # update the number paths for the affected tor switches
        for affected_tor in self.link_id_to_affected_tors[link_id]:
            # self.update_paths_to_core(affected_tor) <-- OLD: inefficient
            # Below is new method that doesn't involve graph traversal
            num_paths_to_core = self.get_num_paths_to_core(affected_tor)
            self.num_paths_to_core[affected_tor] = num_paths_to_core

        # update pod capacity dict
        self.update_pod_capacity_on_link_status_change(link_id, False)

        if self.get_linkguardian_enabled(link_id): # if LG is enabled
            # update the lg_ports_per_pipe for both the switches
            for switch_id in self.linkid_to_switchpair_mapping[link_id]:
                # for loop over the two switches connected by the link
                self.decr_lg_ports_per_pipe(switch_id, link_id)

            # disable LG
            self.set_link_attribute(link_id, "lg_enabled", False)

    def reset_loss_rate(self, link_id) -> None:
        self.set_link_attribute(link_id, "loss_rate", INITIAL_LINK_LOSS_RATE)
        self.set_link_attribute(link_id, "effective_loss_rate", INITIAL_LINK_LOSS_RATE)

    def reset_effective_link_capacity(self, link_id) -> None:
        orig_capacity = self.get_link_capacity(link_id)
        self.set_link_attribute(link_id, "effective_capacity", orig_capacity)

    def enable_link(self, link_id) -> None:
        # Assumption:
        # a lossy link once disabled is NOT enabled again without being repaired
        # so reset the actual and effective loss rates before enabling the link
        self.reset_loss_rate(link_id)

        # Assumption:
        # A disabled link once enabled will be fixed and so no LG running on it.
        # Therefore, reset the effective_capacity before enabling the link
        self.reset_effective_link_capacity(link_id)
        
        self.set_link_attribute(link_id, "disabled", False)

        # remove the link from the dict of disabled links
        self.disabled_links.remove(link_id)

        # since the link is enabled, add loss rate to the total_loss_rate
        self.total_loss_rate += INITIAL_LINK_LOSS_RATE
        self.total_effective_loss_rate += INITIAL_LINK_LOSS_RATE


        # next block first updates the ToR and Agg switch attributes
        # then it re-calculates the paths to core for each affected ToR
        sw1, sw2 = self.linkid_to_switchpair_mapping[link_id]
        sw1_type = self.get_switch_type(sw1)
        sw2_type = self.get_switch_type(sw2)

        switch_pair_types = set([sw1_type, sw2_type])

        if sw1_type == SwitchType.TOR:
            tor_switch = sw1
        elif sw2_type == SwitchType.TOR:
            tor_switch = sw2

        if sw1_type == SwitchType.AGG:
            agg_switch = sw1
        elif sw2_type == SwitchType.AGG:
            agg_switch = sw2

        if sw1_type == SwitchType.CORE:
            core_switch = sw1
        elif sw2_type == SwitchType.CORE:
            core_switch = sw2

        if switch_pair_types == set([SwitchType.TOR, SwitchType.AGG]):
            # it is a ToR-Agg Link
            # For ToR sw: add the agg switch from the list
            self.add_agg_switch_to_tor(tor_switch, agg_switch)

        elif switch_pair_types == set([SwitchType.AGG, SwitchType.CORE]):
            # it is a Agg-Core Link
            # For Agg sw: increment the num_active_uplinks
            self.increment_num_active_uplinks(agg_switch)

        # update the number paths for the affected tor switches
        for affected_tor in self.link_id_to_affected_tors[link_id]:
            # self.update_paths_to_core(affected_tor) <-- OLD: inefficient
            # Below is new method that doesn't involve graph traversal
            num_paths_to_core = self.get_num_paths_to_core(affected_tor)
            self.num_paths_to_core[affected_tor] = num_paths_to_core

        # update pod capacity dict
        self.update_pod_capacity_on_link_status_change(link_id, True)

    def set_link_loss_rate(self, link_id, loss_rate) -> None:
        """ 
        Sets corruption loss rate on an enabled link
        """
        # The link should be enabled
        assert self.is_link_disabled(link_id) == False, "set_link_loss_rate() called on a disabled link"

        orig_loss_rate = self.get_link_attribute(link_id, "loss_rate")
        self.set_link_attribute(link_id, "loss_rate", loss_rate)
        # update the total_loss_rate
        # first, minus the initial value of the link's loss rate
        self.total_loss_rate -= orig_loss_rate
        # then, add the new value of the link's loss rate
        self.total_loss_rate += loss_rate

    def set_link_effective_loss_rate(self, link_id, loss_rate) -> None:
        """ 
        Sets the effective corruption loss rate on an enabled link
        """
        # The link should be enabled
        assert self.is_link_disabled(link_id) == False, "set_link_effective_loss_rate() called on a disabled link"

        orig_effective_loss_rate = self.get_link_attribute(link_id, "effective_loss_rate")
        self.set_link_attribute(link_id, "effective_loss_rate", loss_rate)
        # update the total_effective_loss_rate
        # first, minus the initial value of the link's loss rate
        self.total_effective_loss_rate -= orig_effective_loss_rate
        # then, add the new value of the link's loss rate
        self.total_effective_loss_rate += loss_rate

    def update_pod_capacity_on_link_status_change(self, link_id: int, link_enabled: bool) -> None:
        pod_id = self.link_id_to_pod_id[link_id]
        link_type = self.get_link_type(link_id)
        effective_link_capacity = self.get_effective_link_capacity(link_id)
        pod_capacity_type = linktype_to_pod_capacitytype[link_type]

        if link_enabled: # we need to add capacity
            self.per_pod_capacity[pod_id][pod_capacity_type] += effective_link_capacity
        else: # we need to subtract capacity
            self.per_pod_capacity[pod_id][pod_capacity_type] -= effective_link_capacity

    def update_effective_link_capacity(self, link_id: int, new_effective_capacity: float) -> None:
        # retrieve the curr effective link capacity
        curr_effective_capacity = self.get_effective_link_capacity(link_id)

        # update the new effective link capacity
        self.set_link_attribute(link_id, "effective_capacity", new_effective_capacity)

        pod_id = self.link_id_to_pod_id[link_id]
        link_type = self.get_link_type(link_id)
        pod_capacity_type = linktype_to_pod_capacitytype[link_type]

        # update the per pod capacity type
        self.per_pod_capacity[pod_id][pod_capacity_type] -= curr_effective_capacity
        self.per_pod_capacity[pod_id][pod_capacity_type] += new_effective_capacity



    def get_upstream_switch_id_and_type(self, link_id: int) -> typing.Tuple[int, SwitchType]:
        sw1, sw2 = self.linkid_to_switchpair_mapping[link_id]

        sw1_type = self.get_switch_type(sw1)
        sw2_type = self.get_switch_type(sw2)

        if sw1_type.value > sw2_type.value:
            # sw1 is upstream
            return (sw1, sw1_type)
        else:
            return (sw2, sw2_type)

    def get_connected_switches_of_type(self, link_id: int, type1: SwitchType, type2: SwitchType) -> typing.Tuple[int, int]:
        sw1, sw2 = self.linkid_to_switchpair_mapping[link_id]

        if self.get_switch_type(sw1) == type1:
            type1_sw = sw1
        elif self.get_switch_type(sw2) == type1:
            type1_sw = sw2
        else:
            raise Exception("Link {} is not connected to any switch of type {}".format(link_id, type1.name))

        if self.get_switch_type(sw1) == type2:
            type2_sw = sw1
        elif self.get_switch_type(sw2) == type2:
            type2_sw = sw2
        else:
            raise Exception("Link {} is not connected to any switch of type {}".format(link_id, type2.name))

        return (type1_sw, type2_sw)


    def get_downstream_switch_id_and_type(self, link_id: int) -> typing.Tuple[int, SwitchType]:
        sw1, sw2 = self.linkid_to_switchpair_mapping[link_id]

        sw1_type = self.get_switch_type(sw1)
        sw2_type = self.get_switch_type(sw2)

        if sw1_type.value < sw2_type.value:
            # sw1 is downstream
            return (sw1, sw1_type)
        else:
            return (sw2, sw2_type)


    def get_adjacent_switch_ids(self, switch_id: int, type: SwitchType = SwitchType.ALL) -> set:
        """ 
        Gets the IDs of adjacent switches. Filters by SwitchType if specified.
        """
        adjacent_switch_ids = list(self._graph.neighbors(switch_id))

        if type == SwitchType.ALL:
            adj_switches_of_type = set(adjacent_switch_ids)
        else: # neighbors of only specific type are required
            adj_switches_of_type = set()
            for adj_switch in adjacent_switch_ids:
                if self.get_switch_type(adj_switch) == type:
                    adj_switches_of_type.add(adj_switch)

        return adj_switches_of_type


    def get_paths_to_core_switch(self, tor_id: int, core_id: int) -> list:
        """ 
        Returns a list, where each item is a list of edge IDs (path)
        """
        internal_graph = self.get_internal_graph()
        switch_paths_list = list(nx.simple_paths.all_simple_paths(
            internal_graph, tor_id, core_id, 
            cutoff=(self.tiers - 1))) # cutoff implies max # of hops

        link_paths_list = []

        for switch_path in switch_paths_list:
            link_path = []
            found_disabled_link = False
            for i in range(len(switch_path) - 1):
                switch_pair = (switch_path[i], switch_path[i+1])
                link_id = internal_graph.edges[switch_pair]['id']
                found_disabled_link = self.is_link_disabled(link_id)
                if found_disabled_link:
                    break
                else:
                    link_path.append(link_id)
            if found_disabled_link:
                continue
            else:
                link_paths_list.append(link_path)

        return link_paths_list

    def populate_all_paths_to_core(self, spinner: Spinner) -> None:
        """ 
        Fills up self.paths_to_core dict: tor_id -> [paths list]
        """
        for tor in self.switch_typewise_list[SwitchType.TOR]:
            # iterate over all tor switches
            tor_paths_list = []
            for core in self.switch_typewise_list[SwitchType.CORE]:
                paths_to_core = self.get_paths_to_core_switch(tor, core)
                tor_paths_list.extend(paths_to_core)
                spinner.next()
            
            # populate the global structure
            self.paths_to_core[tor] = tor_paths_list

    def update_paths_to_core(self, tor_id: int) -> None:
        """ 
        [DEPRECATED] since graph traversal in inefficient
        Updates self.paths_to_core and self.num_paths_to_core
        """
        tor_paths_list = []
        for core in self.switch_typewise_list[SwitchType.CORE]:
            paths_to_core = self.get_paths_to_core_switch(tor_id, core)
            tor_paths_list.extend(paths_to_core)

        self.paths_to_core[tor_id] = tor_paths_list
        self.num_paths_to_core[tor_id] = len(tor_paths_list)

    def get_num_paths_to_core(self, tor_id: int, agg_switches_to_exclude: list =[], \
        agg_switches_to_update: dict ={}):
        """ 
        Updates self.paths_to_core and self.num_paths_to_core
        """
        assert self.get_switch_type(tor_id) == SwitchType.TOR, \
            "paths to core always computed from a tor switch"

        # get the list of connected aggregate switches
        agg_switch_list = self.get_connected_agg_switches(tor_id)

        # exclude the agg switches links to which may be disabled
        # typically there should be 0 or just 1 agg switch to exclude
        for agg_to_exclude in agg_switches_to_exclude:
            agg_switch_list.remove(agg_to_exclude)

        num_paths_to_core = 0

        # for each (remaining) connected agg switch, fetch the active uplinks
        agg_active_uplinks = {}
        for agg_switch in agg_switch_list:
            agg_active_uplinks[agg_switch] = self.get_num_active_uplinks(agg_switch)
            
        # update the num_uplinks for specified agg switches
        # this is for AGG-CORE links being considered for disabling
        # For each agg_switch in agg_active_uplinks, 
        # *if* that agg_switch is in agg_switches_to_update, 
        # then update the uplinks        
        for agg_switch in agg_active_uplinks:
            if agg_switch in agg_switches_to_update:
                agg_active_uplinks[agg_switch] = agg_switches_to_update[agg_switch]
        
        # OLD:
        # for agg_switch in agg_switches_to_update:
        #     agg_active_uplinks[agg_switch] = agg_switches_to_update[agg_switch]

        for agg_switch in agg_active_uplinks:
            num_paths_to_core += agg_active_uplinks[agg_switch]

        return num_paths_to_core


    def get_min_num_paths_to_core(self) -> int:
        # min_num_paths = sys.maxsize  # some maximum value
        # for num_paths in self.num_paths_to_core.values():
        #     if num_paths < min_num_paths:
        #         min_num_paths = num_paths
        # return min_num_paths
        return min(self.num_paths_to_core.values())

    def get_avg_num_paths_to_core(self) -> float:
        return sum(self.num_paths_to_core.values()) / self.num_tors

    def get_min_per_pod_capacity_to_core(self) -> float:
        pod_capacities = [min(x) for x in [self.per_pod_capacity[y].values() for y in self.per_pod_capacity]]
        return min(pod_capacities)

    def get_avg_per_pod_capacity_to_core(self) -> float:
        pod_capacities = [min(x) for x in [self.per_pod_capacity[y].values() for y in self.per_pod_capacity]]
        return sum(pod_capacities) / self.num_pods

    def get_max_link_loss_rate(self) -> float:
        return heapq.nlargest(1, self.top_loss_rates_heap)[0]

    def get_max_lg_ports_per_pipe(self) -> int:
        return heapq.nlargest(1, self.top_lg_ports_per_pipe_heap)[0]

    def dump_topo_visualization(self, filename: str) -> None:
        """ 
        Dumps the topology visualization to a file

        Argument:
            filename: str. path to target PDF file
        """
        graph = self.get_internal_graph()
        fig = plt.figure()
        fig.set_figwidth(20)
        fig.set_figheight(10)
        positions = nx.multipartite_layout(graph, subset_key='type', align='horizontal', scale=100)

        # prepare the dict for link_labels
        link_labels = {}
        for link_id in self.linkid_to_switchpair_mapping:
            switch_pair = self.linkid_to_switchpair_mapping[link_id]
            link_labels[switch_pair] = link_id

        nx.draw_networkx_labels(graph, positions, font_color='white')
        nx.draw(graph, pos=positions)
        nx.draw_networkx_edge_labels(graph, pos=positions, 
            edge_labels=link_labels, 
            label_pos=0.2, # to prevent label overlaps
            font_color='red') 
        plt.savefig(filename, bbox_inches='tight')

def check_topo_params(topo_type, topo_params):
    """ 
    Checks if the required topo_params are passed

    Arguments:
        topo_type: enum TopoType
        topo_params: dict with topo params
    
    Returns:
        True: if all required topo params are present
        False: if any topo params are missing
    """
    required_params = TOPO_REQUIRED_PARAMS[topo_type]
    for param in required_params:
        if param not in topo_params:
            print(TERM_ERROR_STR + "{} is missing. Required for {}".format(param, topo_type.name))
            return False
    return True


def build_topo_fattree(topo: Topology, topo_params: dict, spinner: Spinner) -> None:
    params_valid = check_topo_params(TopoType.FatTree, topo_params)
    if(not params_valid):
        print(TERM_ERROR_STR + "exiting as the params are not valid")
        sys.exit(1)
    
    # assign topo_params to Topology class attribute
    topo.topo_params = topo_params

    # extract the params
    k = topo_params['k']
    capacity = topo_params['link_capacity']

    num_core_switches = (k // 2) ** 2
    num_links = pow(k, 3) / 2

    topo.num_links = num_links

    #############################
    ###### Create the pods ######
    #############################
    # maintain list of ToR/Agg switch IDs per pod
    pod_switch_id_dicts = {} # dict of per-pod dicts
    for pod in range(k):
        # init pod capacity dict
        topo.per_pod_capacity[pod] = {PodCapacityType.ToR_to_Agg: 0.0, PodCapacityType.Agg_to_Core: 0.0}

        # add the ToR switches
        tor_switch_ids = []
        for i in range(k // 2):
            added_switch_id = topo.add_switch(SwitchType.TOR, {'pod': pod, 'agg_switches': []})
            tor_switch_ids.append(added_switch_id)
        
        # add the Agg switches
        agg_switch_ids = []
        for i in range(k // 2):
            added_switch_id = topo.add_switch(SwitchType.AGG, {'pod': pod, 'num_active_uplinks': 0})
            agg_switch_ids.append(added_switch_id)

        switch_id_dict = {SwitchType.TOR: tor_switch_ids, SwitchType.AGG: agg_switch_ids}
        pod_switch_id_dicts[pod] = switch_id_dict
        
        # connect every ToR to every Agg switch
        for tor_id in tor_switch_ids:
            for agg_id in agg_switch_ids:
                link_id = topo.add_link(tor_id, agg_id, capacity, {"link_type": LinkType.TOR_AGG})
                # update the link_id to affected_tors mapping
                topo.link_id_to_affected_tors[link_id] = {tor_id}
                # update list of agg_switches for the tor switch
                topo.add_agg_switch_to_tor(tor_id, agg_id)
                # update link_id to pod_id mapping
                topo.link_id_to_pod_id[link_id] = pod
                # update pod capacity dict
                topo.update_pod_capacity_on_link_status_change(link_id, True)

    # Add the core switches
    core_switch_ids = []
    for i in range(num_core_switches):
        added_switch_id = topo.add_switch(SwitchType.CORE)
        core_switch_ids.append(added_switch_id)

    # Connect the core switches to the pods (agg switches)
    #   For each core switch, compute the stride number it belongs to. 
    #   Then for each pod, index the aggr switch list with the stride number 
    #   to get the connected aggr switch.
    for idx in range(num_core_switches):
        core_id = core_switch_ids[idx]
        stride = idx // (k // 2)

        for pod in range(k):
            pod_agg_switch_ids = pod_switch_id_dicts[pod][SwitchType.AGG]
            agg_id = pod_agg_switch_ids[stride]
            link_id = topo.add_link(core_id, agg_id, capacity, {"link_type": LinkType.AGG_CORE})

            # update the num_active_uplinks
            topo.increment_num_active_uplinks(agg_id)

            # update the list of affected tors
            topo.link_id_to_affected_tors[link_id] = topo.get_adjacent_switch_ids(agg_id, SwitchType.TOR)

            # update link_id to pod_id mapping
            topo.link_id_to_pod_id[link_id] = pod

            # update pod capacity dict
            topo.update_pod_capacity_on_link_status_change(link_id, True)


    # Populate paths to core for all tor switches
    topo.populate_all_paths_to_core(spinner)

    # Initialize the topology-wide metrics
    topo.num_tors = len(topo.switch_typewise_list[SwitchType.TOR])
    topo.total_loss_rate = num_links * INITIAL_LINK_LOSS_RATE
    topo.total_effective_loss_rate = topo.total_loss_rate
    topo.num_pods = len(topo.per_pod_capacity)

    for tor_id in topo.switch_typewise_list[SwitchType.TOR]:
        topo.num_paths_to_core[tor_id] = len(topo.paths_to_core[tor_id])

TOPO_BUILDER_FUNCS[TopoType.FatTree] = build_topo_fattree

      
def build_topo_leafspine(topo, topo_params, spinner: Spinner):
    params_valid = check_topo_params(TopoType.LeafSpine, topo_params)
    pass

TOPO_BUILDER_FUNCS[TopoType.LeafSpine] = build_topo_leafspine


def build_topo_fbfabric(topo: Topology, topo_params: dict, spinner: Spinner) -> None:
    params_valid = check_topo_params(TopoType.FbFabric, topo_params)
    if(not params_valid):
        print(TERM_ERROR_STR + "exiting as the params are not valid")
        sys.exit(1)

    # assign topo_params to Topology class attribute
    topo.topo_params = topo_params

    # extract the params
    capacity = topo_params['link_capacity']
    oversubscription = topo_params['oversubscription']
    num_pods = topo_params['num_pods']
    tors_per_pod = topo_params['tors_per_pod']
    deployment_percent = topo_params['deployment_percent']

    topo.log("[FB Fabric] Deployment percent = {}".format(deployment_percent))

    partial_deployment = False  # default
    lg_enabled_pod_ids_set = set()
    lg_disabled_pod_ids_set = set()
    # check for partial deployment
    if deployment_percent != 100:
        partial_deployment = True

        num_lg_enabled_pods = math.ceil(num_pods * deployment_percent / 100)
        pod_ids = list(range(num_pods)) # list of all pod IDs

        partial_deploy_rand_gen.shuffle(pod_ids)

        lg_enabled_pod_ids_set = set(pod_ids[:num_lg_enabled_pods])
        topo.log("Pods with LinkGuardian enabled: {}".format(lg_enabled_pod_ids_set))
        pod_ids_set = set(pod_ids)
        lg_disabled_pod_ids_set = pod_ids_set.difference(lg_enabled_pod_ids_set)
        topo.log("Pods with LinkGuardian DISABLED: {}".format(lg_disabled_pod_ids_set))


    # compute the topo parameters
    core_switches_per_spine_plane = int(tors_per_pod / oversubscription)
    num_links_per_pod = (tors_per_pod * 4) + (4 * core_switches_per_spine_plane)
    topo.num_links = num_pods * num_links_per_pod

    #############################
    ###### Create the pods ######
    #############################
    # maintain list of ToR/Agg switch IDs per pod
    pod_switch_id_dicts = {} # dict of per-pod dicts
    for pod in range(num_pods):
        # both types of links are LG enabled by default
        is_tor_agg_link_lg_enabled = True 
        is_agg_core_link_lg_enabled = True

        if partial_deployment:
            # all agg-core links do not run LG in partial deployment
            is_agg_core_link_lg_enabled = False

            # disable tor-agg links in pods not LG enabled
            if pod in lg_disabled_pod_ids_set:
                is_tor_agg_link_lg_enabled = False
        # NETT RESULT: if partial deployment, if pod in lg_enabled_pod_ids_set
        # then in that pod tor-agg links are LG enabled


        # init pod capacity dict
        topo.per_pod_capacity[pod] = {PodCapacityType.ToR_to_Agg: 0.0, PodCapacityType.Agg_to_Core: 0.0}

        # add the ToR switches
        tor_switch_ids = []
        for i in range(tors_per_pod): # exactly tors_per_pod ToRs per pod 
            added_switch_id = topo.add_switch(SwitchType.TOR, {'pod': pod, 'agg_switches': []})
            tor_switch_ids.append(added_switch_id)
            spinner.next()
        
        # add the Agg switches
        agg_switch_ids = []
        for i in range(4):
            added_switch_id = topo.add_switch(SwitchType.AGG, {'pod': pod, 'num_active_uplinks': 0})
            agg_switch_ids.append(added_switch_id)
            spinner.next()

        switch_id_dict = {SwitchType.TOR: tor_switch_ids, SwitchType.AGG: agg_switch_ids}
        pod_switch_id_dicts[pod] = switch_id_dict
        
        # connect every ToR to every Agg switch
        for tor_id in tor_switch_ids:
            for agg_id in agg_switch_ids:
                link_id = topo.add_link(tor_id, agg_id, capacity, {"link_type": LinkType.TOR_AGG}, is_tor_agg_link_lg_enabled)
                # update the link_id to affected_tors mapping
                topo.link_id_to_affected_tors[link_id] = {tor_id}
                # update list of agg_switches for the tor switch
                topo.add_agg_switch_to_tor(tor_id, agg_id)
                # update link_id to pod_id mapping
                topo.link_id_to_pod_id[link_id] = pod
                # update pod capacity dict
                topo.update_pod_capacity_on_link_status_change(link_id, True)
                spinner.next()

    # Add the spine planes with Core switches in them
    spine_plane_switch_ids = {} # plane_id -> [list of core switch ids]
    for spine_plane_id in range(4): # we have exactly 4 spine planes
        core_sw_ids = []
        for core_sw in range(core_switches_per_spine_plane):
            added_switch_id = topo.add_switch(SwitchType.CORE, {"spine_plane": spine_plane_id})
            core_sw_ids.append(added_switch_id)
            spinner.next()
        spine_plane_switch_ids[spine_plane_id] = core_sw_ids

    # Connect the pod's agg switches to respective spine plane core switches
    for spine_plane_id in spine_plane_switch_ids:
        # get the list of core switches in this spine plane
        core_switches = spine_plane_switch_ids[spine_plane_id]

        # go to each pod and get id of agg sw that belongs to this spine
        # plane
        curr_spine_plane_agg_sw_ids = []
        for pod in pod_switch_id_dicts:
            all_agg_switches = pod_switch_id_dicts[pod][SwitchType.AGG]
            # now index this by the spine_plane_id
            agg_sw_id = all_agg_switches[spine_plane_id]
            curr_spine_plane_agg_sw_ids.append(agg_sw_id)
            spinner.next()

        # now we hv: core sw ids + agg sw ids in this plane
        # let's connect them
        for core_id in core_switches:
            for agg_id in curr_spine_plane_agg_sw_ids:
                pod_id = topo.get_switch_attribute(agg_id, "pod")

                link_id = topo.add_link(core_id, agg_id, capacity, {"link_type": LinkType.AGG_CORE}, is_agg_core_link_lg_enabled)

                # update the num_active_uplinks
                topo.increment_num_active_uplinks(agg_id)

                # update the list of affected tors
                topo.link_id_to_affected_tors[link_id] = topo.get_adjacent_switch_ids(agg_id, SwitchType.TOR)

                # update link_id to pod_id mapping
                topo.link_id_to_pod_id[link_id] = pod_id

                # update pod capacity dict
                topo.update_pod_capacity_on_link_status_change(link_id, True)

                # update the spinner animation
                spinner.next()

    # Populate paths to core for all tor switches
    topo.populate_all_paths_to_core(spinner)

    # Initialize the topology-wide metrics
    topo.num_tors = len(topo.switch_typewise_list[SwitchType.TOR])
    topo.total_loss_rate = topo.num_links * INITIAL_LINK_LOSS_RATE
    topo.total_effective_loss_rate = topo.total_loss_rate
    topo.num_pods = len(topo.per_pod_capacity)

    for tor_id in topo.switch_typewise_list[SwitchType.TOR]:
        topo.num_paths_to_core[tor_id] = len(topo.paths_to_core[tor_id])

TOPO_BUILDER_FUNCS[TopoType.FbFabric] = build_topo_fbfabric


