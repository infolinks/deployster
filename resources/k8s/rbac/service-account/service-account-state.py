#!/usr/bin/env python3

import json
import subprocess
import sys


def main():
    stdin: dict = json.loads(sys.stdin.read())
    dependencies: dict = stdin['dependencies']

    project_id = dependencies['namespace']['dependencies']['cluster']['dependencies']['project']['config']['project_id']
    cluster_zone = dependencies['namespace']['dependencies']['cluster']['config']['zone']
    cluster_name = dependencies['namespace']['dependencies']['cluster']['config']['name']
    namespace_name = dependencies['namespace']['config']['name']
    service_account_name = stdin['config']['name']

    # authenticate to the cluter
    # TODO: authenticate to given cluster using cluster.masterAuth.<clusterCaCertificate|clientCertificate|clientKey>
    command = f"gcloud container clusters get-credentials {cluster_name} --project {project_id} --zone {cluster_zone}"
    process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        print(f"Failed authenticating to cluster: {process.stderr}", file=sys.stderr)
        exit(process.returncode)

    # check if service account exists
    command = f"kubectl get serviceaccount {service_account_name} -n {namespace_name} --ignore-not-found=true -o=json"
    process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        print(f"Failed getting service account '{service_account_name}':\n{process.stderr}", file=sys.stderr)
        exit(1)
    elif process.stdout:
        print(json.dumps({
            'status': 'VALID',
            'properties': json.loads(process.stdout)
        }, indent=2))
    else:
        print(json.dumps({
            'status': 'MISSING',
            'actions': [
                {
                    'name': 'create-service-account',
                    'description': f"Create service-account '{service_account_name}'",
                    'entrypoint': '/deployster/create-service-account.py',
                    'args': [
                        '--project-id', project_id,
                        '--zone', cluster_zone,
                        '--name', cluster_name,
                        '--namespace', namespace_name,
                        '--service-account', service_account_name
                    ]
                }
            ]
        }, indent=2))


if __name__ == "__main__":
    main()
