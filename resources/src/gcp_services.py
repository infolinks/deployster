import json
from time import sleep
from typing import Sequence

from googleapiclient.discovery import build

services = {}


def region_from_zone(zone: str) -> str:
    return zone[0:zone.rfind('-')]


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


def get_sql():
    return get_service('sqladmin', 'v1beta4')


def get_iam():
    return get_service('iam', 'v1')


def get_compute():
    return get_service('compute', 'v1')


def get_container():
    return get_service('container', 'v1')


def get_project_enabled_apis(project_id: str) -> Sequence[str]:
    result: dict = get_service_management().services().list(consumerId=f'project:{project_id}').execute()
    apis: Sequence[dict] = result['services'] if 'services' in result else []
    return [api['serviceName'] for api in apis]


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


def wait_for_compute_region_operation(project_id, region, operation, timeout=300):
    operations_service = get_compute().regionOperations()

    interval = 5
    counter = 0
    while True:
        sleep(interval)
        counter = counter + interval

        result = operations_service.get(project=project_id, region=region, operation=operation['name']).execute()

        if 'status' in result and result['status'] == 'DONE':
            if 'error' in result:
                raise Exception("ERROR: %s" % json.dumps(result['error']))
            else:
                return result
        if counter >= timeout:
            raise Exception(f"Timed out waiting for Google Compute regional operation: {json.dumps(result,indent=2)}")


def wait_for_compute_global_operation(project_id, operation, timeout=300):
    operations_service = get_compute().globalOperations()

    interval = 5
    counter = 0
    while True:
        sleep(interval)
        counter = counter + interval

        result = operations_service.get(project=project_id, operation=operation['name']).execute()

        if 'status' in result and result['status'] == 'DONE':
            if 'error' in result:
                raise Exception("ERROR: %s" % json.dumps(result['error']))
            else:
                return result
        if counter >= timeout:
            raise Exception(f"Timed out waiting for Google Compute global operation: {json.dumps(result,indent=2)}")


def wait_for_compute_zonal_operation(project_id, zone, operation, timeout=300):
    operations_service = get_compute().zoneOperations()

    interval = 5
    counter = 0
    while True:
        sleep(interval)
        counter = counter + interval

        result = operations_service.get(project=project_id, zone=zone, operation=operation['name']).execute()

        if 'status' in result and result['status'] == 'DONE':
            if 'error' in result:
                raise Exception("ERROR: %s" % json.dumps(result['error']))
            else:
                return result
        if counter >= timeout:
            raise Exception(f"Timed out waiting for Google Compute zonal operation: {json.dumps(result,indent=2)}")


def wait_for_container_projects_zonal_operation(project_id, zone, operation, timeout=300):
    operations_service = get_container().projects().zones().operations()

    interval = 5
    counter = 0
    while True:
        sleep(interval)
        counter = counter + interval

        result = operations_service.get(projectId=project_id, zone=zone, operationId=operation['name']).execute()

        if 'status' in result and result['status'] == 'DONE':
            if 'error' in result:
                raise Exception("ERROR: %s" % json.dumps(result['error']))
            else:
                return result
        if counter >= timeout:
            raise Exception(
                f"Timed out waiting for Google Kubernetes Engine zonal operation: {json.dumps(result,indent=2)}")


def wait_for_sql_operation(project_id, operation, timeout=60 * 30):
    operations_service = get_sql().operations()

    interval = 5
    counter = 0
    while True:
        sleep(interval)
        counter = counter + interval

        result = operations_service.get(project=project_id, operation=operation['name']).execute()

        if 'status' in result and result['status'] == 'DONE':
            if 'error' in result:
                raise Exception("ERROR: %s" % json.dumps(result['error']))
            else:
                return result
        if counter >= timeout:
            raise Exception(f"Timed out waiting for Google Cloud SQL operation: {json.dumps(result,indent=2)}")
