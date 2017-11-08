#!/usr/bin/env python3

import argparse
import json

from googleapiclient.discovery import build

from deployster.gcp.services import wait_for_resource_manager_operation


def main():
    argparser = argparse.ArgumentParser(description='Attach GCP project to organization.')
    argparser.add_argument('--project-id', dest='project_id', required=True, metavar='PROJECT-ID',
                           help="the GCP project ID (eg. 'western-evening', or 'backoffice')")
    argparser.add_argument('--organization-id', type=int, dest='organization_id', required=True,
                           metavar='ORGANIZATION-ID',
                           help="the numeric ID of the organization to create the project in.")
    args = argparser.parse_args()

    cloud_resource_manager = build(serviceName='cloudresourcemanager', version='v1')
    result = cloud_resource_manager.projects().update(projectId=args.project_id, body={
        "parent": {
            'type': 'organization',
            'id': str(args.organization_id)
        }
    }).execute()
    project = wait_for_resource_manager_operation(result)
    print(json.dumps({'project': project}))


if __name__ == "__main__":
    main()
