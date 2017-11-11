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
    namespace = properties['namespace']
    namespace_name = namespace['metadata']['name'] if isinstance(namespace, dict) else str(namespace)
    service_account_name = properties['name']

    # TODO: authenticate to given cluster using cluster.masterAuth.<clusterCaCertificate|clientCertificate|clientKey>
    #       we can use kubectl to create custom cluster, user & context to this cluster

    command = f"kubectl get serviceaccount {service_account_name} " \
              f"                    --namespace {namespace_name} " \
              f"                    --ignore-not-found=true " \
              f"                    --output=json"
    process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if process.returncode != 0:
        state = {
            'status': 'INVALID',
            'reason': f"Failed getting service-account '{service_account_name}':\n{process.stderr}"
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
                    'name': 'create-service-account',
                    'description': f"Create service-account '{service_account_name}'",
                    'entrypoint': '/deployster/create-service-account.py',
                    'args': [
                        '--project-id', project_id,
                        '--zone', zone,
                        '--cluster-name', cluster_name,
                        '--namespace', namespace_name,
                        '--service-account', service_account_name
                    ]
                }
            ],
            'properties': {}
        }

    print(json.dumps(state))


if __name__ == "__main__":
    main()
