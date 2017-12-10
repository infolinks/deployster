import json
import os
import re
import sys
from typing import Mapping, Sequence, Union, Tuple, MutableSequence

from gcp_services import GcpServices


def load_scenarios(scenario_pattern: str) -> Sequence[Tuple[dict, dict, dict]]:
    print("", file=sys.stderr)
    scenarios: MutableSequence[Tuple[dict, dict, dict]] = []
    for scenario_file in os.listdir('./tests/scenarios'):
        if re.match(scenario_pattern, scenario_file):
            file_name = os.path.join('./tests/scenarios', scenario_file)
            print(f"Loading GCP project scenario '{file_name}'...", file=sys.stderr)
            with open(file_name, 'r') as f:
                scenario_data = json.loads(f.read())
                scenario_tuple = (scenario_data['actual'], scenario_data['config'], scenario_data['expected'])
                scenarios.append(scenario_tuple)
    return scenarios


class MockGcpServices(GcpServices):
    def __init__(self,
                 projects: Mapping[str, dict],
                 project_billing_infos: Mapping[str, dict],
                 project_apis: Mapping[str, Sequence[str]]) -> None:
        super().__init__()
        self._projects: Mapping[str, dict] = projects
        self._project_billing_infos: Mapping[str, dict] = project_billing_infos
        self._project_apis: Mapping[str, Sequence[str]] = project_apis

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
