import json
import sys
import time
from time import sleep

from dateutil import parser
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


def get_deployment_manager():
    return get_service('deploymentmanager', 'v2')


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


def wait_for_google_deployment_manager_operation(project_id, op):
    operations_service = get_deployment_manager().operations()
    while op['status'] != 'DONE':
        time.sleep(3)
        op = operations_service.get(project=project_id, operation=op['name']).execute()

    # print run duration
    duration_seconds = (parser.parse(op['endTime']) - parser.parse(op['startTime'])).seconds
    hours = str(duration_seconds / 60 / 60).rjust(2, '0')
    minutes = str(duration_seconds / 60 % 60).rjust(2, '0')
    seconds = str(duration_seconds % 60).rjust(2, '0')
    sys.stderr.write(op['status'] + ' (ran for ' + hours + ':' + minutes + ':' + seconds + ')\n')

    # parse output and fail if the operation failed
    failed = False
    if 'statusMessage' in op:
        sys.stderr.write('Result: ' + op['statusMessage'] + '\n')
    if 'warnings' in op and len(op['warnings']):
        sys.stderr.write('Warnings: ' + json.dumps(op['warnings']) + '\n')
    if 'httpErrorStatusCode' in op:
        failed = True
        http_error = str(op['httpErrorStatusCode']) + ' (' + op['httpErrorMessage'] + ')'
        sys.stderr.write('HTTP error: ' + http_error + '\n')
    if 'error' in op and 'errors' in op['error'] and len(op['error']['errors']):
        failed = True
        sys.stderr.write(str(len(op['error']['errors'])) + ' errors:\n')
        for error in op['error']['errors']:
            code = error['code'] if 'code' in error else 'UNKNOWN_ERROR'
            message = error['message'] if 'message' in error else 'UNKNOWN ERROR'
            sys.stderr.write('* %s error at %s: %s\n' % (code, error['location'], message))
    if failed:
        time.sleep(1)
        sys.stdout.flush()
        sys.stderr.flush()
        raise Exception("operation failed (see errors above)")


def collect_project_static_ips(project_id):
    sys.stderr.write("Fetching all static IP addresses for project '%s'...\n" % project_id)

    result = get_compute().addresses().aggregatedList(project=project_id, maxResults=500).execute()

    project_addresses = {}
    for region in result['items'].values():
        if 'addresses' in region:
            for addr in region['addresses']:
                addr_name = addr['name']
                ip_address = addr['address']
                project_addresses[addr_name] = ip_address
    return project_addresses
