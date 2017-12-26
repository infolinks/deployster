import time
from pathlib import Path
from typing import Mapping, Sequence, Union, Any, Tuple

from docker import DockerInvoker
from external_services import ExternalServices, SqlExecutor
from util import Logger


class MockDockerInvoker(DockerInvoker):

    def __init__(self,
                 volumes: Sequence[str] = None,
                 return_code: int = -1,
                 stderr: str = '',
                 stdout: str = '') -> None:
        super().__init__(volumes)
        self._mock_return_code = return_code
        self._mock_stderr = stderr
        self._mock_stdout = stdout

    def _invoke(self, local_work_dir: Path, container_work_dir: str, image: str, entrypoint: str = None,
                args: Sequence[str] = None, input: dict = None, stderr_logger: Logger = None,
                stdout_logger: Logger = None) -> Tuple[int, str, str]:
        return self._mock_return_code, self._mock_stdout, self._mock_stderr


class MockSqlExecutor(SqlExecutor):

    def __init__(self, svc: ExternalServices, sql_execution_results: Mapping[str, Sequence[dict]] = None) -> None:
        super().__init__(svc=svc)
        self._sql_execution_results = sql_execution_results

    def open(self) -> None:
        pass

    def close(self) -> None:
        pass

    def execute_sql(self, sql: str):
        return self._sql_execution_results[sql]

    def execute_sql_script(self, path: str):
        pass


class MockExternalServices(ExternalServices):

    def __init__(self,
                 gcloud_access_token: str = 'random-string-here',
                 gcp_projects: Mapping[str, dict] = None,
                 gcp_project_billing_infos: Mapping[str, dict] = None,
                 gcp_project_apis: Mapping[str, Sequence[str]] = None,
                 gcp_iam_service_accounts: Mapping[str, dict] = None,
                 gcp_iam_policies: Mapping[str, dict] = None,
                 gcp_sql_tiers: Mapping[str, dict] = None,
                 gcp_sql_flags: Mapping[str, dict] = None,
                 gcp_sql_instances: Mapping[str, dict] = None,
                 gcp_sql_execution_results: Mapping[str, Sequence[dict]] = None,
                 gcp_sql_users: Mapping[str, Sequence[dict]] = None,
                 gke_clusters: Mapping[str, dict] = None,
                 gke_server_config: Mapping[str, Any] = None,
                 gcp_compute_regional_ip_addresses: Mapping[str, Any] = None,
                 gcp_compute_global_ip_addresses: Mapping[str, Any] = None,
                 k8s_objects: Mapping[str, dict] = None,
                 k8s_create_times: Mapping[str, int] = None) -> None:
        super().__init__()
        self._gcloud_access_token: str = gcloud_access_token
        self._gcp_projects: Mapping[str, dict] = gcp_projects
        self._gcp_project_billing_infos: Mapping[str, dict] = gcp_project_billing_infos
        self._gcp_project_apis: Mapping[str, Sequence[str]] = gcp_project_apis
        self._gcp_iam_service_accounts: Mapping[str, dict] = gcp_iam_service_accounts
        self._gcp_iam_policies: Mapping[str, dict] = gcp_iam_policies
        self._gcp_sql_tiers = gcp_sql_tiers
        self._gcp_sql_flags = gcp_sql_flags
        self._gcp_sql_instances = gcp_sql_instances
        self._gcp_sql_execution_results = gcp_sql_execution_results
        self._gcp_sql_users = gcp_sql_users
        self._gke_clusters = gke_clusters
        self._gke_server_config = gke_server_config
        self._gcp_compute_regional_ip_addresses = gcp_compute_regional_ip_addresses
        self._gcp_compute_global_ip_addresses = gcp_compute_global_ip_addresses
        self._k8s_objects: Mapping[str, dict] = k8s_objects
        self._k8s_create_times: Mapping[str, int] = k8s_create_times

    def _get_gcp_service(self, service_name, version) -> Any:
        raise NotImplementedError()

    def find_gcp_project(self, project_id: str) -> Union[None, dict]:
        return self._gcp_projects[project_id] if project_id in self._gcp_projects else None

    def find_gcp_project_billing_info(self, project_id: str) -> Union[None, dict]:
        return self._gcp_project_billing_infos[project_id] if project_id in self._gcp_project_billing_infos else None

    def update_gcp_project_billing_info(self, project_id: str, body: dict) -> None:
        pass

    def find_gcp_project_enabled_apis(self, project_id: str) -> Sequence[str]:
        return self._gcp_project_apis[project_id] if project_id in self._gcp_project_apis else None

    def wait_for_gcp_service_manager_operation(self, result):
        pass

    def enable_gcp_project_api(self, project_id: str, api: str) -> None:
        pass

    def disable_gcp_project_api(self, project_id: str, api: str) -> None:
        pass

    def wait_for_gcp_resource_manager_operation(self, result):
        pass

    def create_gcp_project(self, body: dict) -> None:
        pass

    def update_gcp_project(self, project_id: str, body: dict) -> None:
        pass

    def find_service_account(self, project_id: str, email: str):
        key: str = f"projects/{project_id}/serviceAccounts/{email}"
        return self._gcp_iam_service_accounts[key] if key in self._gcp_iam_service_accounts else None

    def create_service_account(self, project_id: str, email: str, display_name: str):
        pass

    def update_service_account_display_name(self, project_id: str, email: str, display_name: str, etag: str):
        pass

    def get_project_iam_policy(self, project_id: str):
        return self._gcp_iam_policies[project_id] if project_id in self._gcp_iam_policies else None

    def update_project_iam_policy(self, project_id: str, etag: str, bindings: Sequence[dict], verbose: bool = False):
        pass

    def get_gcp_sql_allowed_tiers(self, project_id: str) -> Mapping[str, dict]:
        return self._gcp_sql_tiers

    def get_gcp_sql_allowed_flags(self) -> Mapping[str, dict]:
        return self._gcp_sql_flags

    def get_gcp_sql_instance(self, project_id: str, instance_name: str):
        return self._gcp_sql_instances[instance_name] if instance_name in self._gcp_sql_instances else None

    def get_gcp_sql_users(self, project_id: str, instance_name: str) -> Sequence[dict]:
        key = f"{project_id}-{instance_name}"
        return self._gcp_sql_users[key] if key in self._gcp_sql_users else None

    def create_gcp_sql_instance(self, project_id: str, body: dict) -> None:
        pass

    def patch_gcp_sql_instance(self, project_id: str, instance: str, body: dict) -> None:
        pass

    def update_gcp_sql_user(self, project_id: str, instance: str, password: str) -> None:
        pass

    def wait_for_gcp_sql_operation(self, project_id: str, operation: dict, timeout=60 * 30):
        pass

    def create_gcp_sql_executor(self, **kwargs) -> SqlExecutor:
        return MockSqlExecutor(svc=self, sql_execution_results=self._gcp_sql_execution_results)

    def create_gcp_sql_user(self, project_id: str, instance_name: str, user_name: str, password: str) -> None:
        pass

    def get_gke_cluster(self, project_id: str, zone: str, name: str):
        key = f"{project_id}-{zone}-{name}"
        return self._gke_clusters[key] if key in self._gke_clusters else None

    def get_gke_cluster_node_pool(self, project_id: str, zone: str, name: str, pool_name: str):
        cluster = self.get_gke_cluster(project_id=project_id, zone=zone, name=name)
        if cluster is not None and 'nodePools' in cluster:
            try:
                return [pool for pool in cluster['nodePools'] if pool['name'] == pool_name][0]
            except IndexError:
                pass
        return None

    def get_gke_server_config(self, project_id: str, zone: str) -> Mapping[str, Any]:
        return self._gke_server_config

    def create_gke_cluster(self, project_id: str, zone: str, body: dict, timeout: int = 60 * 15):
        pass

    def update_gke_cluster_master_version(self, project_id: str, zone: str, name: str, version: str,
                                          timeout: int = 60 * 15):
        pass

    def update_gke_cluster(self, project_id: str, zone: str, name: str, body: dict, timeout: int = 60 * 15):
        pass

    def update_gke_cluster_legacy_abac(self, project_id: str, zone: str, name: str, body: dict, timeout: int = 60 * 15):
        pass

    def update_gke_cluster_monitoring(self, project_id: str, zone: str, name: str, body: dict, timeout: int = 60 * 15):
        pass

    def update_gke_cluster_logging(self, project_id: str, zone: str, name: str, body: dict, timeout: int = 60 * 15):
        pass

    def update_gke_cluster_addons(self, project_id: str, zone: str, name: str, body: dict, timeout: int = 60 * 15):
        pass

    def create_gke_cluster_node_pool(self, project_id: str, zone: str, name: str, node_pool_body: dict,
                                     timeout: int = 60 * 15):
        pass

    def update_gke_cluster_node_pool(self, project_id: str, zone: str, cluster_name: str, pool_name: str, body: dict,
                                     timeout: int = 60 * 15):
        pass

    def update_gke_cluster_node_pool_management(self, project_id: str, zone: str, cluster_name: str, pool_name: str,
                                                body: dict, timeout: int = 60 * 15):
        pass

    def update_gke_cluster_node_pool_autoscaling(self, project_id: str, zone: str, cluster_name: str, pool_name: str,
                                                 body: dict, timeout: int = 60 * 15):
        pass

    def wait_for_gke_zonal_operation(self, project_id: str, zone: str, operation: dict,
                                     timeout: int = 60 * 15):
        pass

    def generate_gcloud_access_token(self, json_credentials_file: Path) -> str:
        return self._gcloud_access_token

    def get_gcp_compute_regional_ip_address(self, project_id: str, region: str, name: str) -> Union[None, dict]:
        key = f"{project_id}-{region}-{name}"
        return self._gcp_compute_regional_ip_addresses[key] if key in self._gcp_compute_regional_ip_addresses else None

    def create_gcp_compute_regional_ip_address(self, project_id: str, region: str, name: str, timeout: int = 60 * 5):
        pass

    def wait_for_gcp_compute_regional_operation(self, project_id: str, region: str, operation: dict,
                                                timeout: int = 60 * 5):
        pass

    def get_gcp_compute_global_ip_address(self, project_id: str, name: str) -> Union[None, dict]:
        key = f"{project_id}-{name}"
        return self._gcp_compute_global_ip_addresses[key] if key in self._gcp_compute_global_ip_addresses else None

    def create_gcp_compute_global_ip_address(self, project_id: str, name: str, timeout: int = 60 * 5):
        pass

    def wait_for_gcp_compute_global_operation(self, project_id: str, operation: dict, timeout: int = 60 * 5):
        pass

    def find_k8s_cluster_object(self, manifest: dict) -> Union[None, dict]:
        api_version: str = manifest["apiVersion"]
        kind: str = manifest["kind"]
        metadata: dict = manifest["metadata"]
        name: str = metadata["name"]
        key: str = f"{api_version}-{kind}-{name}"
        return self._k8s_objects[key] if key in self._k8s_objects else None

    def find_k8s_namespace_object(self, manifest: dict) -> Union[None, dict]:
        api_version: str = manifest["apiVersion"]
        kind: str = manifest["kind"]
        metadata: dict = manifest["metadata"]
        name: str = metadata["name"]
        namespace: str = metadata["namespace"]
        key = f"{api_version}-{kind}-{namespace}-{name}"
        return self._k8s_objects[key] if key in self._k8s_objects else None

    def create_k8s_object(self, manifest: dict, timeout: int = 60 * 5, verbose: bool = True) -> None:
        api_version: str = manifest["apiVersion"]
        kind: str = manifest["kind"]
        metadata: dict = manifest["metadata"]
        name: str = metadata["name"]
        if 'namespace' in metadata:
            name: str = metadata['namespace'] + '-' + name
        key = f"{api_version}-{kind}-{name}"
        if self._k8s_create_times is not None and key in self._k8s_create_times:
            duration: int = self._k8s_create_times[key]
            time.sleep(duration / 1000)

    def update_k8s_object(self, manifest: dict, timeout: int = 60 * 5, verbose: bool = True) -> None:
        api_version: str = manifest["apiVersion"]
        kind: str = manifest["kind"]
        metadata: dict = manifest["metadata"]
        name: str = metadata["name"]
        if 'namespace' in metadata:
            name: str = metadata['namespace'] + '-' + name
        key = f"{api_version}-{kind}-{name}"
        if self._k8s_create_times is not None and key in self._k8s_create_times:
            duration: int = self._k8s_create_times[key]
            time.sleep(duration / 1000)
