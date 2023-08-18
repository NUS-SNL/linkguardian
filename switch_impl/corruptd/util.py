import json 

def is_json(json_file):
    try:
        json.loads(json_file)
    except ValueError as e:
        return False
    return True 

def json_to_dict(obj):
    return json.loads(obj)

def dict_to_json(obj):
    return json.dumps(obj)

def msg_corrupted(target, downstream_sw, dev_port, mcast_grp, action):
    j = dict()
    j['event'] = target
    j['switch_id'] = downstream_sw
    j['dev_port'] = dev_port
    j['mcast_grp'] = mcast_grp
    j['action'] = action
    return j

# def msg_protected(upstream_sw, dev_port):
#     j = dict()
#     j['event'] = EVENT_PROTECTED_LINK
#     j['switch_id'] = upstream_sw
#     j['dev_port'] = dev_port
#     return j

# def msg_activate(upstream_sw, dev_port):
#     j = dict()
#     j['event'] = EVENT_ACTIVATE_PROTECTION
#     j['switch_id'] = upstream_sw
#     j['dev_port'] = dev_port
#     return j



