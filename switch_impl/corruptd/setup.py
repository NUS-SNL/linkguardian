'''
Use this tool to load/ update the topology to Redis
'''

import redis
import argparse
from util import dict_to_json, json_to_dict

def main(args):
    clear = args.clear
    topo = args.topo
    redis_endpoint = args.redis_endpoint
    
    r = redis.StrictRedis(redis_endpoint, 6379, charset="utf-8", decode_responses=True)
    
    if clear:
        print('Flushing Redis...')
        r.flushdb()

    if topo:
        print('Loading', topo, 'into Redis...')
        topo_json = None
        with open(topo, 'r') as f:
            topo_json = f.read()
        topo_dict = json_to_dict(topo_json)
        topo_json = dict_to_json(topo_dict)

        curr_ver = r.get('topo_ver')
        if r.get('topo_ver') == None:
            r.set('topo_ver', 1) 
        else:
            r.set('topo_ver', int(curr_ver) + 1)
        r.set("topo", topo_json)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--clear', default=False, action='store_true',
        help='clear all states in Redis'
    )

    parser.add_argument(
        '--topo', required=False,
        help='topology in json'
    )

    parser.add_argument(
        '--redis-endpoint', required=False, default='localhost',
        help='redis endpoint '
    )
    args = parser.parse_args()

    main(args)




