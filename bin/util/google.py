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
    print op['status'] + ' (ran for ' + hours + ':' + minutes + ':' + seconds + ')'

    # parse output and fail if the operation failed
    failed = False
    if 'statusMessage' in op:
        print 'Result: ' + op['statusMessage']
    if 'warnings' in op and len(op['warnings']):
        print 'Warnings: ' + json.dumps(op['warnings'])
    if 'httpErrorStatusCode' in op:
        failed = True
        http_error = str(op['httpErrorStatusCode']) + ' (' + op['httpErrorMessage'] + ')'
        print 'HTTP error: ' + http_error
    if 'error' in op and 'errors' in op['error'] and len(op['error']['errors']):
        failed = True
        print str(len(op['error']['errors'])) + ' errors:'
        for error in op['error']['errors']:
            code = error['code'] if 'code' in error else 'UNKNOWN_ERROR'
            message = error['message'] if 'message' in error else 'UNKNOWN ERROR'
            print '* %s error at %s: %s' % (code, error['location'], message)
    if failed:
        time.sleep(1)
        sys.stdout.flush()
        sys.stderr.flush()
        raise Exception("operation failed (see errors above)")
