import sys
import math
import heapq
from itertools import combinations


sys.path.append("../")
from solutions.solution_base import *
from solutions.corropt_recovery import get_corropt_recovery_event

class CandidateSubsetQueue(object):
    def __init__(self) -> None:
        self._queue = []

    def is_not_empty(self):
        return len(self._queue) > 0

    def add(self, remaining_loss_rate: float, link_subset: set) -> None:
        heapq.heappush(self._queue, (remaining_loss_rate, link_subset))

    def get_least_lossrate_subset(self) -> typing.Tuple[float, set]:
        if self.is_not_empty():
            return heapq.heappop(self._queue)
        else:
            raise Exception("get_least_lossrate_subset() called on an empty CandidateSubsetQueue")


class CorrOptSolution(SolutionBase):
    def __init__(self, topo: Topology, sol_params: dict, sim_logger: SimulationLogger) -> None:
        super().__init__(topo, sol_params, "CorrOpt", sim_logger)

        # convert capacity constraint into min_active_paths
        # Step 1: get the initial active paths for any 1 ToR (symmetric topos,
        # of course!)
        capacity_constraint_percent = sol_params["capacity_constraint_percent"]
        any_tor_id = self.topo.switch_typewise_list[SwitchType.TOR][0]
        initial_paths_to_core = self.topo.get_num_paths_to_core(any_tor_id)

        self.min_active_paths_constraint = math.ceil(initial_paths_to_core * capacity_constraint_percent / 100)

        # track corrupting links that could not be disabled
        # UPDATE: corrupting links now tracked by topo.corrupting_links
        # self.curr_active_corrupting_links = set([])

        self.early_rejects = 0

        # solution stats initialization
        self.sol_summary_stats["Fast checker: failed to disable"] = 0

        self.log("Initialized with per-tor min active paths constraint of {}".format(self.min_active_paths_constraint))

    def log_tor_capacity_constraints_summary(self, tor_id: int) -> None:
        paths_to_core = self.topo.paths_to_core[tor_id]
        total_paths = len(paths_to_core)

        disabled_link_to_inactive_paths = {}
        inactive_paths = []
        for path in paths_to_core:
            for link in path:
                if self.topo.is_link_disabled(link):
                    if link not in disabled_link_to_inactive_paths:
                        disabled_link_to_inactive_paths[link] = [path]
                    else:
                        disabled_link_to_inactive_paths[link].append(path)
                    if path not in inactive_paths:
                        inactive_paths.append(path)
        self.log("Disabled link --> inactive path(s):")
        for disabled_link in disabled_link_to_inactive_paths:
            self.log("{} --> {}".format(disabled_link, " ".join(map(lambda x: str(x), disabled_link_to_inactive_paths[disabled_link]))))

        num_inactive_paths = len(inactive_paths)
        num_active_paths = total_paths - num_inactive_paths
        percent_paths = num_active_paths/total_paths * 100
        self.log("ToR {}: curr paths to core = {}/{} ({}%)".format(tor_id, num_active_paths, total_paths, percent_paths))
        

    def corropt_fast_checker(self, event: LinkEvent) -> LinkEvent:
        # Basic idea:
        # "If" the corrupting link is disabled, check 
        # if all the affected ToRs meet the self.min_active_paths_constraint
        # if so, then 'actually' disable the link and return the recovery event 
        # For the recovery event: get the lead time from corropt_recovery
        
        # get the affected link_id
        link_id = event.link_id

        # get the list of affected tors
        affected_tor_set = self.topo.link_id_to_affected_tors[link_id]

        # link_type = self.topo.get_link_type(link_id)

        # get the downstream switch's id and type
        sw_id, sw_type = self.topo.get_downstream_switch_id_and_type(link_id)

        can_disable_link_safely = True 

        self.log("Curr disabled links [{}]: {}".format(len(self.topo.disabled_links), self.topo.disabled_links))
        if sw_type == SwitchType.AGG:
            # need to reduce active uplinks on this agg switch
            # then check if affected ToRs meet the capacity constraint
            curr_active_uplinks = self.topo.get_num_active_uplinks(sw_id)
            new_active_uplinks = curr_active_uplinks - 1
            agg_uplink_update_dict = {sw_id: new_active_uplinks}

            # check capacity constraint on all affected ToRs
            for affected_tor in affected_tor_set:
                paths_to_core = self.topo.get_num_paths_to_core(affected_tor, [], agg_uplink_update_dict)
                if paths_to_core < self.min_active_paths_constraint:
                    can_disable_link_safely = False
                    # record the link that could not be disabled
                    # UPDATE: no need to add as simulation.py would hv 
                    # already updated topo.corrupting_links
                    # self.curr_active_corrupting_links.add(link_id)
                    break

        elif sw_type == SwitchType.TOR:
            # find the agg_id to exclude from the ToR's uplink paths
            agg_id, agg_type = self.topo.get_upstream_switch_id_and_type(link_id)
            agg_exclude_list = [agg_id]

            # check capacity constraint on all affected ToRs
            for affected_tor in affected_tor_set:
                # NOTE: there should be just 1 ToR in the affected list
                paths_to_core = self.topo.get_num_paths_to_core(affected_tor, agg_exclude_list, {})
                if paths_to_core < self.min_active_paths_constraint:
                    can_disable_link_safely = False
                    # self.log("ToR {} breaks capacity constraint. CANNOT DISABLE link {}.".format(affected_tor, link_id))
                    # self.log_tor_capacity_constraints_summary(affected_tor)
                    # self.log("Topo's total loss rate after disabling: {}".format(self.topo.total_loss_rate))
                    
                    # record the link that could not be disabled
                    # UPDATE: no need to add as simulation.py would hv 
                    # already updated topo.corrupting_links
                    # self.curr_active_corrupting_links.add(link_id)
                    break

        if can_disable_link_safely:
            self.topo.disable_link(link_id)
            
            # remove the link if present in curr_active_corrupting_links
            # this happens when previously failed-to-disable link fails again
            # and this time we are able to disable it
            # UPDATE: no need for this since corrupting link would be added to
            # topo.corrupting_links on a failure event and above disable_link()
            # call would have removed the link from topo.corrupting_links
            # if link_id in self.curr_active_corrupting_links:
            #     self.curr_active_corrupting_links.remove(link_id)

            recovery_event = get_corropt_recovery_event(link_id, event.time)
            self.log("Disabled Link {}. Scheduling recovery at time {}".format(link_id, recovery_event.time))
            self.log("Topo's total loss rate: {}".format(self.topo.total_loss_rate))
            return recovery_event
        else: # cannot disable the link safely
            # return a NopeEvent
            self.log("ToR {} breaks capacity constraint. CANNOT DISABLE link {}.".format(affected_tor, link_id))
            self.log_tor_capacity_constraints_summary(affected_tor)
            self.log("Topo's curr total loss rate: {}".format(self.topo.total_loss_rate))
            self.sol_summary_stats["Fast checker: failed to disable"] += 1
            return LinkEvent(-1, LinkEventType.NopEvent, -1, -1)

    def get_all_corrupting_link_subsets(self, link_total_set) -> list[typing.Iterable]:
        all_iterables = []
        set_length = len(link_total_set)
        # since singular links are already checked, start from combo len 2 to entire total set
        for length in range(2, set_length+1): # gives len as 1 to set_length-1
            # all_subsets.extend([set(x) for x in combinations(link_total_set,length)])
            curr_length_combinations = combinations(link_total_set, length)
            all_iterables.append(curr_length_combinations)

        # if len(all_iterables) == 0: # happens when single corrupting link
        #     assert set_length == 1, "link_total_set size must be 1"
        #     all_iterables.append([set(link_total_set)])

        return all_iterables


    def get_tors_with_capacity_constraint_violation(self, links_to_disable: set):
        """ 
        Returns a set of ToRs with capacity constraint violation if the given set of
        links were disabled (considers present state of the network)
        """
        agg_switches_to_update = {}
        per_tor_agg_switches_to_exclude = {}
        all_affected_tors = set()

        for link in links_to_disable:
            if self.topo.get_link_type(link) == LinkType.TOR_AGG:
                tor_id, agg_id = self.topo.get_connected_switches_of_type(link, SwitchType.TOR, SwitchType.AGG)
                if tor_id not in per_tor_agg_switches_to_exclude: 
                    per_tor_agg_switches_to_exclude[tor_id] = [agg_id]
                else: # another agg_id for that ToR to exclude
                    per_tor_agg_switches_to_exclude[tor_id].append(agg_id)

            elif self.topo.get_link_type(link) == LinkType.AGG_CORE:
                agg_id, core_id = self.topo.get_connected_switches_of_type(link, SwitchType.AGG, SwitchType.CORE)
                if agg_id not in agg_switches_to_update:
                    agg_switches_to_update[agg_id] = self.topo.get_num_active_uplinks(agg_id) - 1
                else: # already one link for this agg was disabled. Decrease count further
                    agg_switches_to_update[agg_id] -= 1

            affected_tors_for_this_link = self.topo.link_id_to_affected_tors[link]
            for affected_tor in affected_tors_for_this_link:
                all_affected_tors.add(affected_tor) # creating a set

        # self.log("Downstream ToRs: {}".format(all_affected_tors))
        # at this point, we have:
        # (i) agg_switches with updated active uplink counts
        # (ii) per-tor list of agg switches to exclude 
        # (iii) the set of affected (downstream) tor for the given set of links to be disabled

        tors_with_constraint_violation = set()

        for affected_tor in all_affected_tors:
            # prepare agg_switches_to_excludes
            if affected_tor in per_tor_agg_switches_to_exclude:
                agg_switches_to_exclude = per_tor_agg_switches_to_exclude[affected_tor]
            else: # no ToR-Agg link for this switch is disabled
                agg_switches_to_exclude = [] # so no agg sw to exclude

            num_paths_to_core = self.topo.get_num_paths_to_core(affected_tor, agg_switches_to_exclude, agg_switches_to_update)

            if num_paths_to_core < self.min_active_paths_constraint:
                # the tor violates the capacity constraints
                tors_with_constraint_violation.add(affected_tor)

        return tors_with_constraint_violation

    def process_curr_subset_of_links(self, curr_subset: set, reject_cache: list[set], candidate_subset_queue: CandidateSubsetQueue) -> bool:
        is_super_set_of_rejected = False
        for rejected_set in reject_cache:
            if curr_subset.issuperset(rejected_set):
                is_super_set_of_rejected = True
                # self.log("Curr subset is superset of rejected set {}".format(rejected_set))
                # TODO: think if we need to add it to the 
                # reject cache
                # add current set to the reject cache
                # larger subsets will be added to the end. 
                # so smaller sets should get checked first
                # reject_cache.append(curr_subset)
                self.early_rejects += 1
                break

        if is_super_set_of_rejected:
            # no need to check for the remaining loss rate
            # self.log("Skipping curr subset since superset of a reject cache set")
            return False


        # check if disabling the subset violates any capacity constraints
        # self.log("Current subset is not superset of any rejected set")
        # self.log("Checking for capacity constraint violation...")
        tors_with_constraint_violation = self.get_tors_with_capacity_constraint_violation(curr_subset)


        if len(tors_with_constraint_violation) == 0:
            # this subset does not violate constraints 
            # for any ToRs. Let's check the remaining 
            # loss rate (penalty)
            self.log("Curr subset {} does not violate constraints for any ToRs".format(curr_subset))
            loss_rate_reduction = 0
            for link in curr_subset:
                loss_rate_reduction += self.topo.get_link_loss_rate(link)

            remaining_loss_rate = self.topo.total_loss_rate - loss_rate_reduction
            candidate_subset_queue.add(remaining_loss_rate, curr_subset)
            self.log("Candidate subset: {} -> remaining loss rate: {}".format(curr_subset, remaining_loss_rate))
            return True

        else: # else subset violates capacity constraints
            # add it to the reject cache
            self.log("Curr subset {} violates constraints for ToRs: {}".format(curr_subset, tors_with_constraint_violation))
            self.log("Adding it to the reject cache")
            reject_cache.append(curr_subset)
            return False
            

    def corropt_optimizer(self, event: LinkEvent) -> typing.List[LinkEvent]:
        # the recovered link has already been enabled by the simulator
        # this is part of the call back *after* that
        self.log("Running CorrOpt Optimizer...")
        self.log("Curr disabled links [{}]: {}".format(len(self.topo.disabled_links), self.topo.disabled_links))

        recovery_events = []

        if len(self.topo.corrupting_links) == 0:
            # there are no remaining corrupting links in the network
            self.log("No corrupting links. Nothing to optimize...")
            self.log("Topo's total loss rate: {}".format(self.topo.total_loss_rate))
            return recovery_events

        self.log("Current corrupting links: {}".format(self.topo.corrupting_links))
        self.log("Current disabled links: {}".format(self.topo.disabled_links))
        # Step 1: get the ToRs with constraint violation, if all currently corrupting 
        # links are disabled all together

        self.log("Finding ToRs with constraint violation if all corrupting links are disabled...")
        tors_with_constraint_violation = \
            self.get_tors_with_capacity_constraint_violation(self.topo.corrupting_links)

        self.log("ToRs with constraint violation: {}".format(tors_with_constraint_violation))
        
        # Step 2: find the corrupting link(s) which is/are NOT upstream of 
        # the ToRs with capacity violation AND disable them
        self.log("Finding links NOT upstream of these ToRs...")
        links_not_upstream = []
        for link_id in self.topo.corrupting_links.copy():
            affected_tors_for_this_link = self.topo.link_id_to_affected_tors[link_id]
            
            intersection = tors_with_constraint_violation.intersection(affected_tors_for_this_link)

            if len(intersection) == 0:
                # this means that no ToRs downstream of this link 
                # will have constraint violation 
                # if all the currently corrupting links are disabled.
                # So, this link can be safely disabled
                self.topo.disable_link(link_id)
                recovery_events.append(get_corropt_recovery_event(link_id, event.time))
                
                # remove the link from curr_active_corrupting links
                # UPDATE: no more needed as topo.disable_link() will update 
                # topo.corrupting_links
                # if link_id in self.curr_active_corrupting_links:
                #     self.curr_active_corrupting_links.remove(link_id)
                
                links_not_upstream.append(link_id) # mainly for logging

        self.log("Links NOT upstream of constrained ToRs which were disabled: {}".format(links_not_upstream))

        # at this point, the remaining self.curr_active_corrupting_links ('C')
        # are uplink of the tors_with_constraint_violation. Disabling all of
        # these is going to violate capacity constraints of 
        # tors_with_constraint_violation

        self.log("Remaining corrupting links [{}]: {}".format(len(self.topo.corrupting_links), self.topo.corrupting_links))

        if len(self.topo.corrupting_links) == 0:
            # there are no remaining corrupting links in the network
            self.log("No more corrupting links. Nothing more to optimize...")
            self.log("Topo's total loss rate: {}".format(self.topo.total_loss_rate))
            return recovery_events # LinkEvent(-1, LinkEventType.NopeEvent, -1, -1)

        # Step 3: Iterate over all possible subsets of
        # self.curr_active_corrupting_links ('C')
        # shortlist those subsets that do not violate capacity constraint
        # use a reject cache to early reject higher subsets
        reject_cache = [] # init an empty reject cache 
        candidate_subset_queue = CandidateSubsetQueue()
        # all_possible_subset_iterables = self.get_all_corrupting_link_subsets(self.topo.corrupting_links)

        skip_remaining_combinations = False 

        # first go over all single link subsets
        # single_link_subsets = all_possible_subset_iterables[0]
        candidate_single_links_set = set()
        for link in self.topo.corrupting_links:
            curr_subset = {link}
            is_candidate = self.process_curr_subset_of_links(curr_subset, reject_cache, candidate_subset_queue)
            if is_candidate:
                candidate_single_links_set.add(link)

        if not candidate_subset_queue.is_not_empty():
            # this means none of the single link subsets
            # are candidate subsets. Therefore, no other supersets 
            # would be candidate subsets either. We can skip checking for them!
            skip_remaining_combinations = True
            self.log("None of the single link subsets is a candidate. Skipping the rest!")

        if not skip_remaining_combinations:
            # there are some single links which are candidate subsets
            # generate all possible combinations ONLY within these single links
            self.log("Checking remaining combinations of: {}".format(candidate_single_links_set))
            all_possible_subset_iterables = self.get_all_corrupting_link_subsets(candidate_single_links_set)

            # iterate over all remaining subsets
            # for curr_subset in all_possible_subset_iterables:
            subsets_count = 0
            self.early_rejects = 0

            # first go over all iterables
            for curr_combinations in all_possible_subset_iterables:
                # then for each iterable, go over all combinations/subsets
                for curr_combination in curr_combinations:
                    curr_subset = set(curr_combination)
                    # self.log("Checking for subset {}".format(curr_subset))
                    # self.log("Curr reject cache: {}".format(reject_cache))
                    # check if current subset is superset of 
                    # any rejected set in the reject cache
                    self.process_curr_subset_of_links(curr_subset, reject_cache, candidate_subset_queue)
                    subsets_count += 1

            self.log("Processed {} remaining supersets".format(subsets_count))
            self.log("Early rejects: {}".format(self.early_rejects))
                    

        if not candidate_subset_queue.is_not_empty():
            # candidate subset queue is empty
            # means we cannot disable any more links
            self.log("No candidate subsets found that don't violate capacity constraints")
            self.log("Disabled links: {}".format(self.topo.disabled_links))
            self.log("Corrupting links: {}".format(self.topo.corrupting_links))
            self.log("Total loss rate: {}".format(self.topo.total_loss_rate))
            return recovery_events # [LinkEvent(-1, LinkEventType.NopeEvent, -1, -1)]
        
        least_remaining_lossrate, least_subset = candidate_subset_queue.get_least_lossrate_subset()

        self.log("** Least loss rate: {}".format(least_remaining_lossrate))
        self.log("** Corresponding subset: {}". format(least_subset))

        self.log("Disabling the subset...")

        for link in least_subset:
            # disable the link
            self.topo.disable_link(link)
            # schedule the link for recovery
            recovery_events.append(get_corropt_recovery_event(link, event.time))
            # remove the link from curr_active_corrupting links
            # UPDATE: no more needed as topo.disable_link() will update 
            # topo.corrupting_links
            # if link_id in self.curr_active_corrupting_links:
            #     self.curr_active_corrupting_links.remove(link_id)
            
        self.log("Topo's total loss rate after disabling: {}".format(self.topo.total_loss_rate))

        return recovery_events
            

    # overriding the abstract method
    def process_failure_event(self, event: LinkEvent) -> typing.List[LinkEvent]:
        # corropt handles failure events through the fast checker
        requested_event = self.corropt_fast_checker(event)
        return [requested_event]

    
    # overriding the abstract method
    def post_recovery_event_cb(self, event: LinkEvent) -> typing.List[LinkEvent]:
        # this call back is happening after the link is already enabled
        # corropt handles failure events through the optimizer
        returning_events = self.corropt_optimizer(event)

        self.log("Call back returning events: {}".format([x.type.name for x in returning_events]))
        return returning_events
        # return self.corropt_optimizer(event)
