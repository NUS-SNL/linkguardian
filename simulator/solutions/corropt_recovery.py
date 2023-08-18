import sys
import random

sys.path.append("../")
from simulation.link_event import *
from topology.topology import INITIAL_LINK_LOSS_RATE

RAND_SEED = 5469321578 # for reproducible results with same trace + sol
corropt_recovery_rand_gen = random.Random(RAND_SEED)
# print("[CORROPT RECOVERY] Seeded the randint generator")

def get_corropt_recovery_event(link_id: int, curr_time: int) -> LinkEvent:
    # CorrOpt section 7.1:
    # 80% of the links are correctly repaired after 2 days
    # for the remaining, overall it takes a total of 4 days
    rand_val = corropt_recovery_rand_gen.randint(1, 100)
    if rand_val <= 80:
        recovery_delay = 2 * 24 * 3600  # 2 days
    else:
        recovery_delay = 4 * 24 * 3600  # 4 days

    recovery_event_time = curr_time + recovery_delay

    recovery_event = LinkEvent(recovery_event_time, LinkEventType.RecoveryEvent, link_id, INITIAL_LINK_LOSS_RATE)

    return recovery_event

