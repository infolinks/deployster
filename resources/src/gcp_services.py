import json
from time import sleep
from typing import Sequence, MutableMapping, Union, Any, Mapping

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GcpServices:

    def __init__(self) -> None:
        super().__init__()
        self._services: MutableMapping[str, Any] = {}

    def _get_service(self, service_name, version) -> Any:
        service_key = service_name + '_' + version
        if service_key not in self._services:
            self._services[service_key] = build(serviceName=service_name, version=version)
        return self._services[service_key]

    def find_project(self, project_id: str) -> Union[None, dict]:
        filter: str = f"name:{project_id}"
        result: dict = self._get_service('cloudresourcemanager', 'v1').projects().list(filter=filter).execute()

        if 'projects' not in result:
            return None

        projects: Sequence[dict] = result['projects']
        if len(projects) == 0:
            return None
        elif len(projects) > 1:
            raise Exception(f"too many GCP projects matched filter '{filter}'")
        else:
            return projects[0]

    def find_project_billing_info(self, project_id: str) -> Union[None, dict]:
        try:
            service = self._get_service('cloudbilling', 'v1')
            return service.projects().getBillingInfo(name=f"projects/{project_id}").execute()
        except HttpError as e:
            if e.resp.status == 404:
                return None
            else:
                raise

    def find_project_enabled_apis(self, project_id: str) -> Sequence[str]:
        service = self._get_service('servicemanagement', 'v1')
        result: dict = service.services().list(consumerId=f'project:{project_id}').execute()
        if 'services' in result:
            return [api['serviceName'] for api in result['services']]
        else:
            return []

    def create_project(self, body: dict) -> None:
        service = self._get_service('cloudresourcemanager', 'v1').projects()
        self.wait_for_resource_manager_operation(service.create(body=body).execute())

    def update_project(self, project_id: str, body: dict) -> None:
        service = self._get_service('cloudresourcemanager', 'v1').projects()
        self.wait_for_resource_manager_operation(service.update(projectId=project_id, body=body).execute())

    def update_project_billing_info(self, project_id: str, body: dict) -> None:
        service = self._get_service('cloudbilling', 'v1').projects()
        service.updateBillingInfo(name=f'projects/{project_id}', body=body).execute()

    def enable_project_api(self, project_id: str, api: str) -> None:
        self.wait_for_service_manager_operation(
            self._get_service('servicemanagement', 'v1').services().enable(serviceName=api, body={
                'consumerId': f"project:{project_id}"
            }).execute())

    def disable_project_api(self, project_id: str, api: str) -> None:
        self.wait_for_service_manager_operation(
            self._get_service('servicemanagement', 'v1').services().disable(serviceName=api, body={
                'consumerId': f"project:{project_id}"
            }).execute())

    def wait_for_service_manager_operation(self, result):
        if 'response' in result:
            return result['response']

        operations_service = self._get_service('servicemanagement', 'v1').operations()
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

    def wait_for_resource_manager_operation(self, result):
        if 'response' in result:
            return result['response']

        operations_service = self._get_service('cloudresourcemanager', 'v1').operations()
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

    def get_sql_allowed_tiers(self, project_id: str) -> Mapping[str, str]:
        return {tier['tier']: tier
                for tier in self._get_service('sqladmin', 'v1beta4').tiers().list(project=project_id).execute()['items']
                if tier['tier'].startswith('db-')}

    def get_sql_allowed_flags(self) -> Mapping[str, str]:
        service = self._get_service('sqladmin', 'v1beta4')
        return {flag['name']: flag for flag in service.flags().list(databaseVersion='MYSQL_5_7').execute()['items']}

    def get_sql_instance(self, project_id: str, instance_name: str):
        result = self._get_service('sqladmin', 'v1beta4').instances().list(project=project_id).execute()
        if 'items' in result:
            for instance in result['items']:
                if instance['name'] == instance_name:
                    return instance
        return None

    def create_sql_instance(self, project_id: str, body: dict) -> None:
        try:
            op = self._get_service('sqladmin', 'v1beta4').instances().insert(project=project_id, body=body).execute()
            self.wait_for_sql_operation(project_id=project_id, operation=op)
        except HttpError as e:
            status = e.resp.status
            if status == 409:
                raise Exception(f"failed creating SQL instance, possibly due to instance name reuse (you can't "
                                f"reuse an instance name for a week after its deletion)") from e

    def patch_sql_instance(self, project_id: str, instance: str, body: dict) -> None:
        service = self._get_service('sqladmin', 'v1beta4')
        op = service.instances().patch(project=project_id, instance=instance, body=body).execute()
        self.wait_for_sql_operation(project_id=project_id, operation=op)

    def update_sql_user(self, project_id: str, instance: str, password: str) -> None:
        service = self._get_service('sqladmin', 'v1beta4')
        op = service.users().update(project=project_id, instance=instance, host='%', name='root', body={
            'password': password
        }).execute()
        self.wait_for_sql_operation(project_id=project_id, operation=op)

    def wait_for_sql_operation(self, project_id: str, operation: dict, timeout=60 * 30):
        operations_service = self._get_service('sqladmin', 'v1beta4').operations()

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


services = {}


def region_from_zone(zone: str) -> str:
    return zone[0:zone.rfind('-')]


def get_service(service_name, version):
    service_key = service_name + '_' + version
    if service_key not in services:
        services[service_key] = build(serviceName=service_name, version=version)
    return services[service_key]


def get_iam():
    return get_service('iam', 'v1')


def get_compute():
    return get_service('compute', 'v1')


def get_container():
    return get_service('container', 'v1')


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
