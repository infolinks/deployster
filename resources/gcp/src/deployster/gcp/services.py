import json
from time import sleep

from googleapiclient.discovery import build

services = {}


def get_service(service_name, version):
    service_key = service_name + '_' + version
    if service_key not in services:
        services[service_key] = build(serviceName=service_name, version=version)
    return services[service_key]


def get_service_management():
    return get_service('servicemanagement', 'v1')


def get_billing():
    return get_service('cloudbilling', 'v1')


def get_resource_manager():
    return get_service('cloudresourcemanager', 'v1')


def get_iam():
    return get_service('iam', 'v1')


def get_compute():
    return get_service('compute', 'v1')


def wait_for_resource_manager_operation(result):
    if 'response' in result:
        return result['response']

    operations_service = get_resource_manager().operations()
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


def wait_for_service_manager_operation(result):
    if 'response' in result:
        return result['response']

    operations_service = get_service_management().operations()
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
