#!/usr/bin/env python2

import argparse
import json
import sys

import os

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
                           default=os.environ['GCP_ORG_ID'] if 'GCP_ORG_ID' in os.environ else None,
                           help='numerical ID of the Google organization the project belongs to; can be set through '
                                'the GCP_ORG_ID environment variable.')
    argparser.add_argument('--billing-account-id',
                           metavar='ID',
                           default=os.environ[
                               'GCP_BILLING_ACCOUNT_ID'] if 'GCP_BILLING_ACCOUNT_ID' in os.environ else None,
                           help='numerical ID of the Google billing account to assign the project to; can be set '
                                'the GCP_BILLING_ACCOUNT_ID environment variable.')
    argparser.add_argument('--gcr-project',
                           dest='gcr_project_id',
                           metavar='PROJECT',
                           default=os.environ['GCP_GCR_PROJECT_ID'] if 'GCP_GCR_PROJECT_ID' in os.environ else None,
                           help='name of the GCP project to hold/provide the Google Container Registry; can be set '
                                'through the GCP_GCR_PROJECT_ID environment variable.')
    argparser.add_argument('--project',
                           dest='project_id',
                           metavar='PROJECT',
                           default=os.environ['GCP_PROJECT_ID'] if 'GCP_PROJECT_ID' in os.environ else None,
                           help='name of the GCP project to hold the deployment environment, eg. "acme-my-feature"; '
                                'can be set through the GCP_PROJECT_ID environment variable.')
    argparser.add_argument('--env',
                           metavar='NAME',
                           default=os.environ['ENV_NAME'] if 'ENV_NAME' in os.environ else None,
                           help='logical name of the environment being deployed to, eg. "my-feature"; can be set '
                                'through the ENV_NAME environment variable.')
    argparser.add_argument('files',
                           metavar='FILE',
                           nargs='+',
                           help='list of JSON files to build the environment configuration from')
    args = argparser.parse_args()

    # validate required arguments; while we could just add "required=True" to the "add_argument(..)" calls above, that
    # would force the user to specify them on the command line EVEN WHEN the user specifies them through environemtn
    # variables; there's unfortunately no "required unless specified as env-var" flag for "add_argument(..)" :)
    if not args.org_id:
        sys.stderr.write("please specify '--org-id' or set the GCP_ORG_ID environment variable\n")
        sys.stderr.flush()
        argparser.print_usage()
        exit(1)
    elif not args.billing_account_id:
        sys.stderr.write(
            "please specify '--billing-account-id' or set the GCP_BILLING_ACCOUNT_ID environment variable\n")
        sys.stderr.flush()
        argparser.print_usage()
        exit(1)
    elif not args.gcr_project_id:
        sys.stderr.write("please specify '--gcr-project' or set the GCP_GCR_PROJECT_ID environment variable\n")
        sys.stderr.flush()
        argparser.print_usage()
        exit(1)
    elif not args.project_id:
        sys.stderr.write("please specify '--project' or set the GCP_PROJECT_ID environment variable\n")
        sys.stderr.flush()
        argparser.print_usage()
        exit(1)
    elif not args.env:
        sys.stderr.write("please specify '--env' or set the ENV_NAME environment variable\n")
        sys.stderr.flush()
        argparser.print_usage()
        exit(1)

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
