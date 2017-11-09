#!/usr/bin/env python3

import json
import sys

from googleapiclient.errors import HttpError

from deployster.gcp.services import get_compute, wait_for_compute_region_operation


def main():
    params = json.loads(sys.stdin.read())
    project_id = params['properties']['project']['project_id']
    region = params['properties']['region']
    address_name = params['name']

    try:
        op = get_compute().addresses().get(project=project_id, region=region, address=address_name).execute()
        print(json.dumps(op, indent=2), file=sys.stderr)
        state = {
            'status': 'VALID',
            'actions': [],
            'properties': wait_for_compute_region_operation(op)
        }

    except HttpError as e:
        if e.resp.status == 404:
            state = {
                'status': 'MISSING',
                'actions': [
                    {
                        'name': 'create-address',
                        'description': f"Create GCP address",
                        'entrypoint': '/deployster/create-address.py',
                        'args': [
                            '--project-id', project_id,
                            '--region', region,
                            '--name', address_name
                        ]
                    }
                ]
            }
        else:
            state = {
                'status': 'INVALID',
                'reason': str(e)
            }

    print(json.dumps(state))


if __name__ == "__main__":
    main()
