import json
import subprocess
import sys
from abc import abstractmethod
from pathlib import Path
from time import sleep
from typing import Sequence, MutableMapping, Union, Any, Mapping

import pymysql
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pymysql import Connection


class SqlExecutor:

    def __init__(self, gcp_services: 'GcpServices') -> None:
        super().__init__()
        self._gcp: 'GcpServices' = gcp_services

    @abstractmethod
    def open(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    def execute_sql(self, sql: str):
        raise NotImplementedError()

    @abstractmethod
    def execute_sql_script(self, path: str):
        raise NotImplementedError()


class ProxySqlExecutor(SqlExecutor):

    def __init__(self, gcp_services: 'GcpServices', project_id: str, instance: str, password: str, region: str) -> None:
        super().__init__(gcp_services)
        self._project_id: str = project_id
        self._instance: str = instance
        self._username: str = 'root'
        self._password: str = password
        self._region: str = region
        self._proxy_process: subprocess.Popen = None
        self._connection: Connection = None

    def open(self) -> None:
        self._gcp.update_sql_user(project_id=self._project_id, instance=self._instance, password=self._password)
        self._proxy_process: subprocess.Popen = \
            subprocess.Popen([f'/usr/local/bin/cloud_sql_proxy',
                              f'-instances={self._project_id}:{self._region}:{self._instance}=tcp:3306',
                              f'-credential_file=/deployster/service-account.json'])
        try:
            self._proxy_process.wait(2)
            raise Exception(f"could not start Cloud SQL Proxy!")
        except subprocess.TimeoutExpired:
            pass

        print(f"Connecting to MySQL...", file=sys.stderr)
        self._connection: Connection = pymysql.connect(host='localhost',
                                                       port=3306,
                                                       user=self._username,
                                                       password=self._password,
                                                       db='INFORMATION_SCHEMA',
                                                       charset='utf8mb4',
                                                       cursorclass=pymysql.cursors.DictCursor)

    def close(self) -> None:
        try:
            self._connection.close()
        finally:
            self._proxy_process.terminate()

    def execute_sql(self, sql: str) -> Sequence[dict]:
        with self._connection.cursor() as cursor:
            cursor.execute(sql)
            return [row for row in cursor.fetchall()]

    def execute_sql_script(self, path: str):
        command = \
            f"/usr/bin/mysql --user={self._username} " \
            f"               --password={self._password} " \
            f"               --host=127.0.0.1 information_schema < {path}"
        subprocess.run(command, shell=True, check=True)


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

    def create_sql_executor(self, **kwargs) -> SqlExecutor:
        return ProxySqlExecutor(gcp_services=self,
                                project_id=kwargs['project_id'],
                                instance=kwargs['instance'],
                                password=kwargs['password'],
                                region=kwargs['region'])

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

    def get_gke_cluster(self, project_id: str, zone: str, name: str):
        clusters_service = get_service('container', 'v1').projects().zones().clusters()
        try:
            return clusters_service.get(projectId=project_id, zone=zone, clusterId=name).execute()
        except HttpError as e:
            if e.resp.status == 404:
                return None
            else:
                raise

    def get_gke_cluster_node_pool(self, project_id: str, zone: str, name: str, pool_name: str):
        clusters_service = get_service('container', 'v1').projects().zones().clusters()
        try:
            return clusters_service.nodePools().get(projectId=project_id,
                                                    zone=zone,
                                                    clusterId=name,
                                                    nodePoolId=pool_name).execute()
        except HttpError as e:
            if e.resp.status == 404:
                return None
            else:
                raise

    def get_gke_server_config(self, project_id: str, zone: str) -> dict:
        service = get_service('container', 'v1')
        return service.projects().zones().getServerconfig(projectId=project_id, zone=zone).execute()

    def create_gke_cluster(self, project_id: str, zone: str, body: dict, timeout: int = 60 * 15):
        clusters_service = get_service('container', 'v1').projects().zones().clusters()
        op = clusters_service.create(projectId=project_id, zone=zone, body=body).execute()
        self.wait_for_gke_zonal_operation(project_id=project_id, zone=zone, operation=op, timeout=timeout)

    def update_gke_cluster_master_version(self,
                                          project_id: str,
                                          zone: str,
                                          name: str,
                                          version: str,
                                          timeout: int = 60 * 15):
        clusters_service = get_service('container', 'v1').projects().zones().clusters()
        body = {'masterVersion': version}
        op = clusters_service.master(projectId=project_id, zone=zone, clusterId=name, body=body).execute()
        self.wait_for_gke_zonal_operation(project_id=project_id, zone=zone, operation=op, timeout=timeout)

    def update_gke_cluster(self, project_id: str, zone: str, name: str, body: dict, timeout: int = 60 * 15):
        clusters_service = get_service('container', 'v1').projects().zones().clusters()
        op = clusters_service.update(projectId=project_id, zone=zone, clusterId=name, body=body).execute()
        self.wait_for_gke_zonal_operation(project_id=project_id, zone=zone, operation=op, timeout=timeout)

    def update_gke_cluster_legacy_abac(self, project_id: str, zone: str, name: str, body: dict, timeout: int = 60 * 15):
        clusters_service = get_service('container', 'v1').projects().zones().clusters()
        op = clusters_service.legacyAbac(projectId=project_id, zone=zone, clusterId=name, body=body).execute()
        self.wait_for_gke_zonal_operation(project_id=project_id, zone=zone, operation=op, timeout=timeout)

    def update_gke_cluster_monitoring(self, project_id: str, zone: str, name: str, body: dict, timeout: int = 60 * 15):
        clusters_service = get_service('container', 'v1').projects().zones().clusters()
        op = clusters_service.monitoring(projectId=project_id, zone=zone, clusterId=name, body=body).execute()
        self.wait_for_gke_zonal_operation(project_id=project_id, zone=zone, operation=op, timeout=timeout)

    def update_gke_cluster_logging(self, project_id: str, zone: str, name: str, body: dict, timeout: int = 60 * 15):
        clusters_service = get_service('container', 'v1').projects().zones().clusters()
        op = clusters_service.logging(projectId=project_id, zone=zone, clusterId=name, body=body).execute()
        self.wait_for_gke_zonal_operation(project_id=project_id, zone=zone, operation=op, timeout=timeout)

    def update_gke_cluster_addons(self, project_id: str, zone: str, name: str, body: dict, timeout: int = 60 * 15):
        clusters_service = get_service('container', 'v1').projects().zones().clusters()
        op = clusters_service.addons(projectId=project_id, zone=zone, clusterId=name, body=body).execute()
        self.wait_for_gke_zonal_operation(project_id=project_id, zone=zone, operation=op, timeout=timeout)

    def create_gke_cluster_node_pool(self,
                                     project_id: str,
                                     zone: str,
                                     name: str,
                                     node_pool_body: dict,
                                     timeout: int = 60 * 15):
        pools_service = get_service('container', 'v1').projects().zones().clusters().nodePools()
        op = pools_service.create(projectId=project_id,
                                  zone=zone,
                                  clusterId=name,
                                  body={"nodePool": node_pool_body}).execute()
        self.wait_for_gke_zonal_operation(project_id=project_id, zone=zone, operation=op, timeout=timeout)

    def update_gke_cluster_node_pool(self,
                                     project_id: str,
                                     zone: str,
                                     cluster_name: str,
                                     pool_name: str,
                                     body: dict, timeout: int = 60 * 15):
        pools_service = get_service('container', 'v1').projects().zones().clusters().nodePools()
        op = pools_service.update(projectId=project_id,
                                  zone=zone,
                                  clusterId=cluster_name,
                                  nodePoolId=pool_name,
                                  body=body).execute()
        self.wait_for_gke_zonal_operation(project_id=project_id, zone=zone, operation=op, timeout=timeout)

    def update_gke_cluster_node_pool_management(self,
                                                project_id: str,
                                                zone: str,
                                                cluster_name: str,
                                                pool_name: str,
                                                body: dict, timeout: int = 60 * 15):
        pools_service = get_service('container', 'v1').projects().zones().clusters().nodePools()
        op = pools_service.setManagement(projectId=project_id,
                                         zone=zone,
                                         clusterId=cluster_name,
                                         nodePoolId=pool_name,
                                         body=body).execute()
        self.wait_for_gke_zonal_operation(project_id=project_id, zone=zone, operation=op, timeout=timeout)

    def update_gke_cluster_node_pool_autoscaling(self,
                                                 project_id: str,
                                                 zone: str,
                                                 cluster_name: str,
                                                 pool_name: str,
                                                 body: dict, timeout: int = 60 * 15):
        pools_service = get_service('container', 'v1').projects().zones().clusters().nodePools()
        op = pools_service.autoscaling(projectId=project_id,
                                       zone=zone,
                                       clusterId=cluster_name,
                                       nodePoolId=pool_name,
                                       body=body).execute()
        self.wait_for_gke_zonal_operation(project_id=project_id, zone=zone, operation=op, timeout=timeout)

    def wait_for_gke_zonal_operation(self, project_id: str, zone: str, operation: dict,
                                     timeout: int = 60 * 15):
        operations_service = get_service('container', 'v1').projects().zones().operations()

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
                raise Exception(f"Timed out waiting for GKE zonal operation: {json.dumps(result,indent=2)}")

    def generate_gcloud_access_token(self, json_credentials_file: Path) -> str:
        # first, make gcloud use our service account
        command = f"gcloud auth activate-service-account --key-file={json_credentials_file}"
        subprocess.run(command, check=True, shell=True)

        # extract our service account's GCP access token
        process = subprocess.run(f"gcloud auth print-access-token", check=True, shell=True, stdout=subprocess.PIPE)
        return process.stdout.decode('utf-8').strip()


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
