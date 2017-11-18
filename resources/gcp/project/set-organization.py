#!/usr/bin/env python3

import argparse

from googleapiclient.discovery import build

from deployster.gcp.services import wait_for_resource_manager_operation


def main():
    argparser: argparse.ArgumentParser = argparse.ArgumentParser(description='Attach GCP project to organization.')
    argparser.add_argument('--project-id', required=True, metavar='ID', help="the alpha-numeric GCP project ID")
    argparser.add_argument('--organization-id', type=int, metavar='ID', help="the numeric GCP ID of the organization")
    args = argparser.parse_args()

    if args.organization_id:
        parent = {
            'type': 'organization',
            'id': str(args.organization_id)
        }
    else:
        parent = None

    cloud_resource_manager = build(serviceName='cloudresourcemanager', version='v1')
    result = cloud_resource_manager.projects().update(projectId=args.project_id, body={"parent": parent}).execute()
    wait_for_resource_manager_operation(result)


if __name__ == "__main__":
    main()
