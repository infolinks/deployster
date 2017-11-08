#!/usr/bin/env python3

import argparse
import json

from googleapiclient.discovery import build

from deployster.gcp.services import wait_for_resource_manager_operation


def main():
    argparser = argparse.ArgumentParser(description='Create GCP project.')
    argparser.add_argument('--project-id', dest='project_id', required=True, metavar='PROJECT-ID',
                           help="the GCP project ID (eg. 'western-evening', or 'backoffice')")
    argparser.add_argument('--name', dest='project_name', required=True, metavar='PROJECT-NAME',
                           help="the project's user-visible name (eg. 'Backoffice systems')")
    argparser.add_argument('--organization-id', type=int, dest='organization_id', metavar='ORGANIZATION-ID',
                           help="the numeric ID of the organization to create the project in.")
    args = argparser.parse_args()

    request_body = {
        "projectId": args.project_id,
        "name": args.project_name
    }

    if args.organization_id:
        request_body['parent'] = {
            'type': 'organization',
            'id': str(args.organization_id)
        }

    result = build(serviceName='cloudresourcemanager', version='v1').projects().create(body=request_body).execute()
    project = wait_for_resource_manager_operation(result)
    print(json.dumps({'project': project}))


if __name__ == "__main__":
    main()
