#!/usr/bin/env python3

import json
import sys

from googleapiclient.errors import HttpError

from deployster.gcp.services import get_compute


def main():
    params = json.loads(sys.stdin.read())
    project_id = params['properties']['project']['project_id']
    region = params['properties']['region']
    address_name = params['name']

    try:
        addr = get_compute().addresses().get(project=project_id, region=region, address=address_name).execute()
        state = {
            'status': 'VALID',
            'actions': [],
            'properties': {
                'id': addr['id'],
                'name': addr['name'],
                'description': addr['description'],
                'address': addr['address'],
                'status': addr['status'],
                'region': region,
            }
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
