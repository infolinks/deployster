#!/usr/bin/env python3

import argparse
import subprocess


def main():
    argparser = argparse.ArgumentParser(description='Create Kubernetes service-account.')
    argparser.add_argument('--project-id', dest='project_id', required=True, metavar='PROJECT-ID',
                           help="the GCP project ID (eg. 'western-evening', or 'backoffice')")
    argparser.add_argument('--zone', required=True, metavar='ZONE', help="the primary zone of the target cluster.")
    argparser.add_argument('--cluster-name', required=True, metavar='CLUSTER-NAME', help="the GKE cluster name.")
    argparser.add_argument('--namespace', metavar='NAME', help="the name of the namespace to create the account in.")
    argparser.add_argument('--service-account', metavar='NAME', help="the name of the service account to create.")
    args = argparser.parse_args()

    # TODO: authenticate to given cluster using cluster.masterAuth.<clusterCaCertificate|clientCertificate|clientKey>

    command = f"kubectl create serviceaccount {args.service_account} --namespace {args.namespace} --output=json"
    process = subprocess.run(command, shell=True)
    exit(process.returncode)


if __name__ == "__main__":
    main()
