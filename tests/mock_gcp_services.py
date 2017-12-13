import json
import os
import re
import sys
from pathlib import Path
from typing import Mapping, Sequence, Union, Tuple, MutableSequence, Any

from gcp_services import GcpServices, SqlExecutor


def load_scenarios(scenarios_dir: str, scenario_pattern: str) -> Sequence[Tuple[str, dict, dict, dict]]:
    print("", file=sys.stderr)
    scenarios: MutableSequence[Tuple[str, dict, dict, dict]] = []
    for scenario_file in os.listdir(scenarios_dir):
        if re.match(scenario_pattern, scenario_file):
            file_name = os.path.join(scenarios_dir, scenario_file)
            print(f"Loading GCP project scenario '{file_name}'...", file=sys.stderr)
            with open(file_name, 'r') as f:
                scenario_data = json.loads(f.read())
                scenario_tuple = (scenario_data['description'] if 'description' in scenario_data else 'Missing',
                                  scenario_data['actual'],
                                  scenario_data['config'],
                                  scenario_data['expected'])
                scenarios.append(scenario_tuple)
    return scenarios


class MockSqlExecutor(SqlExecutor):

    def __init__(self, gcp_services: 'GcpServices', sql_execution_results: Mapping[str, Sequence[dict]] = None) -> None:
        super().__init__(gcp_services)
        self._sql_execution_results = sql_execution_results

    def open(self) -> None:
        pass

    def close(self) -> None:
        pass

    def execute_sql(self, sql: str):
        return self._sql_execution_results[sql]

    def execute_sql_script(self, path: str):
        pass


class MockGcpServices(GcpServices):
    def __init__(self,
                 gcloud_access_token: str = 'random-string-here',
                 projects: Mapping[str, dict] = None,
                 project_billing_infos: Mapping[str, dict] = None,
                 project_apis: Mapping[str, Sequence[str]] = None,
                 sql_tiers: Mapping[str, dict] = None,
                 sql_flags: Mapping[str, dict] = None,
                 sql_instances: Mapping[str, dict] = None,
                 sql_execution_results: Mapping[str, Sequence[dict]] = None,
                 gke_clusters: Mapping[str, dict] = None,
                 gke_server_config: Mapping[str, Any] = None) -> None:
        super().__init__()
        self._gcloud_access_token: str = gcloud_access_token
        self._projects: Mapping[str, dict] = projects
        self._project_billing_infos: Mapping[str, dict] = project_billing_infos
        self._project_apis: Mapping[str, Sequence[str]] = project_apis
        self._sql_tiers = sql_tiers
        self._sql_flags = sql_flags
        self._sql_instances = sql_instances
        self._sql_execution_results = sql_execution_results
        self._gke_clusters = gke_clusters
        self._gke_server_config = gke_server_config

    def _get_service(self, service_name, version) -> Any:
        raise NotImplementedError()

    def find_project(self, project_id: str) -> Union[None, dict]:
        return self._projects[project_id] if project_id in self._projects else None

    def find_project_billing_info(self, project_id: str) -> Union[None, dict]:
        return self._project_billing_infos[project_id] if project_id in self._project_billing_infos else None

    def update_project_billing_info(self, project_id: str, body: dict) -> None:
        pass

    def find_project_enabled_apis(self, project_id: str) -> Sequence[str]:
        return self._project_apis[project_id] if project_id in self._project_apis else None

    def wait_for_service_manager_operation(self, result):
        pass

    def enable_project_api(self, project_id: str, api: str) -> None:
        pass

    def disable_project_api(self, project_id: str, api: str) -> None:
        pass

    def wait_for_resource_manager_operation(self, result):
        pass

    def create_project(self, body: dict) -> None:
        pass

    def update_project(self, project_id: str, body: dict) -> None:
        pass

    def get_sql_allowed_tiers(self, project_id: str) -> Mapping[str, dict]:
        return self._sql_tiers

    def get_sql_allowed_flags(self) -> Mapping[str, dict]:
        return self._sql_flags

    def get_sql_instance(self, project_id: str, instance_name: str):
        return self._sql_instances[instance_name] if instance_name in self._sql_instances else None

    def create_sql_instance(self, project_id: str, body: dict) -> None:
        pass

    def patch_sql_instance(self, project_id: str, instance: str, body: dict) -> None:
        pass

    def update_sql_user(self, project_id: str, instance: str, password: str) -> None:
        pass

    def wait_for_sql_operation(self, project_id: str, operation: dict, timeout=60 * 30):
        pass

    def create_sql_executor(self, **kwargs) -> SqlExecutor:
        return MockSqlExecutor(gcp_services=self, sql_execution_results=self._sql_execution_results)

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
