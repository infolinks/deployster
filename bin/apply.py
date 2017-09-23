#!/usr/bin/env python2

import argparse
import json
import sys

from gdm import execute_gdm_configurations
from k8s import apply_kubernetes_state
from util.environment import load_environment
from util.project import setup_project


def main():
    argparser = argparse.ArgumentParser(description='Apply deployment specification to the target GCP environment.')
    argparser.add_argument('--print-only',
                           action='store_true',
                           help='if specified, will only print the merged environment context and quit (exit code 0)')
    argparser.add_argument('--org-id',
                           metavar='ID',
                           type=int,
                           required=True,
                           help='numerical ID of the Google organization the project belongs to')
    argparser.add_argument('--billing-account-id',
                           metavar='ID',
                           required=True,
                           help='numerical ID of the Google billing account to assign the project to')
    argparser.add_argument('--gcr-project',
                           dest='gcr_project_id',
                           metavar='PROJECT',
                           required=True,
                           help='name of the GCP project to hold/provide the Google Container Registry')
    argparser.add_argument('--project',
                           dest='project_id',
                           metavar='PROJECT',
                           required=True,
                           help='name of the GCP project to hold the deployment environment, eg. "acme-my-feature"')
    argparser.add_argument('--env',
                           metavar='NAME',
                           required=True,
                           help='logical name of the environment being deployed to, eg. "my-feature"')
    argparser.add_argument('files',
                           metavar='FILE',
                           nargs='+',
                           help='list of JSON files to build the environment configuration from')
    args = argparser.parse_args()

    # build the environment from the list of JSON files provided
    env = load_environment(args.env, args.files)

    # if print-only, print & exit
    if args.print_only:
        sys.stderr.write("Printing full environment context to stdout and quitting (ok)\n")
        sys.stdout.write(json.dumps(env, indent=2))
        exit(0)

    try:

        # locate/build the GCP project and store it in the environment dictionary
        env['project'] = setup_project(args.org_id, args.billing_account_id, args.gcr_project_id, args.project_id)

        # apply google-deployment-manager configurations
        execute_gdm_configurations(env)

        # apply Kubernetes resources if the 'cluster' key in the environment is non-null
        if 'cluster' in env:
            apply_kubernetes_state(env)

    except Exception:
        sys.stderr.write("Exception encountered - here's the fully merged environment (exception will follow):\n")
        sys.stderr.write(open('.merged-environment.json', mode='r').read() + '\n')
        sys.stdout.flush()
        sys.stderr.flush()
        raise


if __name__ == "__main__":
    main()
