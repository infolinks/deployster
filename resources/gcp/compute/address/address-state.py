#!/usr/bin/env python3

import json
import sys

from googleapiclient.errors import HttpError

from deployster.gcp.services import get_compute


class AddressNotFoundError(Exception):

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


def find_regional_address(project_id: str, region: str, name: str) -> dict:
    try:
        return get_compute().addresses().get(project=project_id, region=region, address=name).execute()
    except HttpError as e:
        if e.resp.status == 404:
            raise AddressNotFoundError(
                f"address '{name}' in region '{region}' could not be found in project '{project_id}'")
        else:
            raise


def main():
    stdin: dict = json.loads(sys.stdin.read())
    cfg: dict = stdin['config']
    dependencies: dict = stdin['dependencies']

    project_id: str = dependencies['project']['config']['project_id']
    region: str = cfg['region']
    name: str = cfg['name']

    try:
        addr: dict = find_regional_address(project_id=project_id, region=region, name=name)
        print(json.dumps({
            'status': 'VALID',
            'properties': addr
        }, indent=2))

    except AddressNotFoundError:
        print(json.dumps({
            'status': 'MISSING',
            'actions': [
                {
                    'name': 'create-address',
                    'description': f"Create GCP regional IP address '{name}'",
                    'entrypoint': '/deployster/create-address.py',
                    'args': [
                        '--project-id', project_id,
                        '--region', region,
                        '--name', name
                    ]
                }
            ]
        }, indent=2))


if __name__ == "__main__":
    main()
