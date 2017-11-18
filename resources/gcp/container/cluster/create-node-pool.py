#!/usr/bin/env python3

import argparse
import json
import sys

from deployster.gcp.gke import DEFAULT_OAUTH_SCOPES
from deployster.gcp.services import get_container, wait_for_container_projects_zonal_operation


def build_node_pool(pool):
    min_node_count = pool['min_size'] if 'min_size' in pool else 1
    return {
        "name": pool['name'],
        "management": {"autoRepair": True, "autoUpgrade": False},
        "initialNodeCount": min_node_count,
        "autoscaling": {
            "minNodeCount": min_node_count,
            "enabled": True,
            "maxNodeCount": pool['max_size'] if 'max_size' in pool else min_node_count,
        },
        "config": {
            "serviceAccount": pool['service_account'] if 'service_account' in pool else None,
            "oauthScopes": pool['oauth_scopes'] if 'oauth_scopes' in pool else DEFAULT_OAUTH_SCOPES,
            "preemptible": pool['preemptible'] if 'preemptible' in pool else True,
            "machineType": pool['machine_type'] if 'machine_type' in pool else 'n1-standard-1',
            "diskSizeGb": pool['disk_size_gb'] if 'disk_size_gb' in pool else 20,
            "tags": pool['tags'] if 'tags' in pool else [],  # GCE network tags
            "metadata": pool['metadata'] if 'metadata' in pool else {},  # GKE nodes metadata entries
            "labels": pool['labels'] if 'labels' in pool else {},  # k8s labels to apply to nodes
        }
    }


def main():
    argparser = argparse.ArgumentParser(description='Create node pool.')
    argparser.add_argument('--project-id', required=True, metavar='ID', help="the alpha-numeric GCP project ID")
    argparser.add_argument('--zone', required=True, metavar='ZONE', help="the primary zone of the cluster")
    argparser.add_argument('--name', required=True, metavar='NAME', help="the name of the cluster")
    argparser.add_argument('--pool', required=True, metavar='NAME', help="the name of the node pool")
    args = argparser.parse_args()

    stdin = json.loads(sys.stdin.read())

    operation = get_container().projects().zones().clusters().nodePools().create(
        projectId=args.project_id, zone=args.zone, clusterId=args.name,
        body={
            "nodePool": build_node_pool(pool) for pool in stdin['config']['node_pools'] if pool['name'] == args.pool
        }).execute()
    wait_for_container_projects_zonal_operation(project_id=args.project_id,
                                                zone=args.zone,
                                                operation=operation,
                                                timeout=900)


if __name__ == "__main__":
    main()