#!/usr/bin/env python3

import argparse

from googleapiclient.discovery import build

from deployster.gcp.services import wait_for_resource_manager_operation


def main():
    argparser: argparse.ArgumentParser = argparse.ArgumentParser(description='Create GCP project.')
    argparser.add_argument('--project-id', required=True, metavar='ID', help="the alpha-numeric GCP project ID")
    argparser.add_argument('--project-name', required=True, metavar='NAME', help="the project's user-visible name")
    argparser.add_argument('--organization-id', type=int, metavar='ID', help="the numeric GCP ID of the organization")
    args = argparser.parse_args()

    result: dict = build(serviceName='cloudresourcemanager', version='v1').projects().create(body={
        "projectId": args.project_id,
        "name": args.project_name,
        "parent": {'type': 'organization', 'id': str(args.organization_id)} if args.organization_id else None
    }).execute()

    wait_for_resource_manager_operation(result)


if __name__ == "__main__":
    main()
