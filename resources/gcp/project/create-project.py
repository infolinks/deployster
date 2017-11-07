#!/usr/bin/env python3

import json
import sys
from time import sleep

from googleapiclient.discovery import build


def wait_for_resource_manager_operation(result):
    if 'response' in result:
        return result['response']

    operations_service = build(serviceName='cloudresourcemanager', version='v1').operations()
    while True:
        sleep(5)
        result = operations_service.get(name=result['name']).execute()
        if 'done' in result and result['done']:
            if 'response' in result:
                return result['response']

            elif 'error' in result:
                raise Exception("ERROR: %s" % json.dumps(result['error']))

            else:
                raise Exception("UNKNOWN ERROR: %s" % json.dumps(result))


def main():
    params = json.loads(sys.stdin.read())
    name = params['name']
    properties = params['properties']

    result = build(serviceName='cloudresourcemanager', version='v1').projects().create(body={
        "projectId": name,
        "name": name,
        "parent": {"type": "organization", "id": str(properties['organization_id'])}
    }).execute()

    sys.stderr.write("Waiting for project creation '%s' to complete...\n" % result['name'])
    project = wait_for_resource_manager_operation(result)

    print(json.dumps(project))


if __name__ == "__main__":
    main()
