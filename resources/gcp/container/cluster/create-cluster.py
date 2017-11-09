#!/usr/bin/env python3

import argparse
import json
import sys

from deployster.gcp.services import get_compute, wait_for_compute_region_operation


def main():
    argparser = argparse.ArgumentParser(description='Create GCP Compute address.')
    argparser.add_argument('--project-id', dest='project_id', required=True, metavar='PROJECT-ID',
                           help="the GCP project ID to create the address in(eg. 'western-evening', or 'backoffice')")
    argparser.add_argument('--region', dest='region', required=True, metavar='REGION',
                           help="the region to create the address in")
    argparser.add_argument('--name', dest='name', required=True, metavar='NAME',
                           help="the reserved IP address name.")
    args = argparser.parse_args()

    params = json.loads(sys.stdin.read())
    name = params['name']
    properties = params['properties']

    request_body = {
        "projectId": name,
        "name": name
    }

    if 'organization_id' in properties:
        request_body['parent'] = {
            'type': 'organization',
            'id': str(properties['organization_id'])
        }

    addresses_service = get_compute().addresses()
    result = addresses_service.insert(project=args.project_id, region=args.region, body={'name': args.name}).execute()
    print(json.dumps(result, indent=2), file=sys.stderr)
    response = wait_for_compute_region_operation(result)
    print(json.dumps({'response': response}))


if __name__ == "__main__":
    main()
