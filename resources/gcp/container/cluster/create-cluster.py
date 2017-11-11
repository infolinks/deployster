#!/usr/bin/env python3

import json
import sys

from deployster.gcp.gke import DEFAULT_OAUTH_SCOPES
from deployster.gcp.services import get_container, wait_for_container_projects_zonal_operation


def build_node_pool(properties, pool):
    min_node_count = pool['min_size'] if 'min_size' in pool else 1
    return {
        "name": pool['name'],
        "version": properties['version'],
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
    params = json.loads(sys.stdin.read())
    properties = params['properties']
    project_id = properties['project']['project_id']
    zone = properties['zone']
    version = properties['version']

    config = get_container().projects().zones().getServerconfig(projectId=project_id, zone=zone).execute()
    if version not in config['validNodeVersions']:
        print(f"version '{version}' is not an acceptable Kubernetes node version in GKE", file=sys.stderr)
        exit(1)
    elif version not in config['validMasterVersions']:
        print(f"version '{version}' is not an acceptable Kubernetes master version in GKE", file=sys.stderr)
        exit(1)

    operation = get_container().projects().zones().clusters().create(projectId=project_id, zone=zone, body={
        "cluster": {
            "name": properties['name'],
            "description": properties['description'],
            "locations": [properties['zone']],
            "initialClusterVersion": version,
            "masterAuth": {"username": ""},
            "masterAuthorizedNetworksConfig": {"enabled": False},
            "legacyAbac": {"enabled": False},
            "monitoringService": "monitoring.googleapis.com",
            "loggingService": "logging.googleapis.com",
            "addonsConfig": {
                "httpLoadBalancing": {"disabled": False},
                "kubernetesDashboard": {"disabled": True},
                "horizontalPodAutoscaling": {"disabled": False},
            },
            "enableKubernetesAlpha": False,
            "nodePools": [build_node_pool(properties, pool) for pool in properties['node_pools']]
        },
    }).execute()

    result = wait_for_container_projects_zonal_operation(project_id=project_id,
                                                         zone=zone,
                                                         operation=operation,
                                                         timeout=900)

    print(json.dumps({'response': result}))


if __name__ == "__main__":
    main()
