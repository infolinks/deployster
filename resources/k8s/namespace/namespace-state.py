#!/usr/bin/env python3

import json
import subprocess
import sys


def main():
    params = json.loads(sys.stdin.read())
    properties = params['properties']
    project_id = properties['project']['project_id']
    zone = properties['cluster']['zone']
    cluster_name = properties['cluster']['name']
    namespace_name = properties['name']

    # TODO: authenticate to given cluster using cluster.masterAuth.<clusterCaCertificate|clientCertificate|clientKey>
    #       we can use kubectl to create custom cluster, user & context to this cluster

    command = f"kubectl get namespace {namespace_name} --ignore-not-found=true --output=json"
    process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if process.returncode != 0:
        state = {
            'status': 'INVALID',
            'reason': f"Failed getting namespace '{namespace_name}':\n{process.stderr}"
        }
    elif process.stdout:
        state = {
            'status': 'VALID',
            'actions': [],
            'properties': json.loads(process.stdout)
        }
    else:
        state = {
            'status': 'MISSING',
            'actions': [
                {
                    'name': 'create-namespace',
                    'description': f"Create namespace '{namespace_name}'",
                    'entrypoint': '/deployster/create-namespace.py',
                    'args': [
                        '--project-id', project_id,
                        '--zone', zone,
                        '--cluster-name', cluster_name,
                        '--namespace', namespace_name
                    ]
                }
            ],
            'properties': {}
        }

    print(json.dumps(state))


if __name__ == "__main__":
    main()
