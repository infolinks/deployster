#!/usr/bin/env python3

import argparse
import subprocess

import sys


def main():
    argparser = argparse.ArgumentParser(description='Create Kubernetes service-account.')
    argparser.add_argument('--project-id', required=True, metavar='ID', help="the alpha-numeric GCP project ID")
    argparser.add_argument('--zone', required=True, metavar='ZONE', help="the primary zone of the cluster")
    argparser.add_argument('--name', required=True, metavar='NAME', help="the name of the cluster")
    argparser.add_argument('--namespace', required=True, metavar='NAME', help="the namespace for the service account")
    argparser.add_argument('--service-account', metavar='NAME', help="the service account to create")
    args = argparser.parse_args()

    project_id = args.project_id
    cluster_zone = args.zone
    cluster_name = args.name

    # authenticate to the cluter
    # TODO: authenticate to given cluster using cluster.masterAuth.<clusterCaCertificate|clientCertificate|clientKey>
    command = f"gcloud container clusters get-credentials {cluster_name} --project {project_id} --zone {cluster_zone}"
    process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        print(f"Failed authenticating to cluster: {process.stderr}", file=sys.stderr)
        exit(process.returncode)

    # create service account
    command = f"kubectl create serviceaccount {args.service_account} -n {args.namespace} -o=json"
    process = subprocess.run(command, shell=True)
    exit(process.returncode)


if __name__ == "__main__":
    main()
