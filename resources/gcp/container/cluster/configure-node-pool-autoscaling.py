#!/usr/bin/env python3

import argparse
import json

from deployster.gcp.services import get_container, wait_for_container_projects_zonal_operation


# TODO: review all arguments to all resource actions (nargs, choices, required, etc)

def main():
    argparser = argparse.ArgumentParser(description='Configure auto-scaling of a node pool.')
    argparser.add_argument('--project-id', dest='project_id', required=True, metavar='PROJECT-ID',
                           help="the GCP project ID (eg. 'western-evening', or 'backoffice')")
    argparser.add_argument('--zone', required=True, metavar='ZONE', help="the zone of the cluster.")
    argparser.add_argument('--name', required=True, metavar='NAME', help="the name of the target cluster.")
    argparser.add_argument('--pool', required=True, metavar='NAME', help="the name of the node pool.")
    argparser.add_argument('--min-size', type=int, required=True, metavar='SIZE',
                           help="minimum number of nodes in the pool.")
    argparser.add_argument('--max-size', type=int, required=True, metavar='SIZE',
                           help="maximum number of nodes in the pool.")
    args = argparser.parse_args()

    op = get_container().projects().zones().clusters().nodePools().autoscaling(
        projectId=args.project_id,
        zone=args.zone,
        clusterId=args.name,
        nodePoolId=args.pool,
        body={
            'autoscaling': {
                'enabled': True,
                'minNodeCount': args.min_size,
                'maxNodeCount': args.max_size
            }
        })
    result = wait_for_container_projects_zonal_operation(project_id=args.project_id, zone=args.zone, operation=op)
    print(json.dumps({'result': result}))


if __name__ == "__main__":
    main()
