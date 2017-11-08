#!/usr/bin/env python3

import json
import sys

from googleapiclient.discovery import build

from deployster.gcp.services import wait_for_resource_manager_operation


def main():
    params = json.loads(sys.stdin.read())

    cloud_resource_manager = build(serviceName='cloudresourcemanager', version='v1')
    result = cloud_resource_manager.projects().update(projectId=params['name'], body={"parent": None}).execute()
    project = wait_for_resource_manager_operation(result)
    print(json.dumps({'project': project}))


if __name__ == "__main__":
    main()
