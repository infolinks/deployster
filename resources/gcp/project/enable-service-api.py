#!/usr/bin/env python3

import json
import sys

from deployster.gcp.services import get_service_management, wait_for_service_manager_operation


def main():
    params = json.loads(sys.stdin.read())

    service_management_service = get_service_management().services()

    op = service_management_service.enable(serviceName=params['properties']['api'],
                                           body={'consumerId': f"project:{params['name']}"}).execute()
    result = wait_for_service_manager_operation(op)
    print(json.dumps({'result': result}))


if __name__ == "__main__":
    main()
