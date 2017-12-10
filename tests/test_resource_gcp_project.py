import json
from typing import Sequence, Union, Mapping

import pytest

from gcp_project import GcpProject
from gcp_services import GcpServices


class MockGcpServices(GcpServices):
    def __init__(self,
                 projects: Mapping[str, dict],
                 project_billing_infos: Mapping[str, dict],
                 project_apis: Mapping[str, dict]) -> None:
        super().__init__()
        self._projects: Mapping[str, dict] = projects
        self._project_billing_infos: Mapping[str, dict] = project_billing_infos
        self._project_apis: Mapping[str, dict] = project_apis

    def find_project(self, project_id: str) -> Union[None, dict]:
        return self._projects[project_id] if project_id in self._projects else None
        # return {
        #     "name": project_id,
        #     "parent": {
        #         "type": "organization",
        #         "id": "123",
        #     },
        #     "projectId": project_id
        # }

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


@pytest.mark.parametrize("billing_account_id", [None, "", "ABC123"])
@pytest.mark.parametrize("enabled_apis", [None, [], ["api1"], ["api1", "api2"]])
@pytest.mark.parametrize("disabled_apis", [None, [], ["api1"], ["api2", "api3"]])
def test_project_does_not_exist(capsys,
                                billing_account_id: str,
                                enabled_apis: Sequence[str],
                                disabled_apis: Sequence[str]):
    data: dict = {
        'name': 'test',
        'type': 'test-resource',
        'version': '1.2.3',
        'verbose': True,
        'workspace': '/workspace',
        'config': {
            'project_id': 'my-project'
        },
        'staleState': {}
    }
    expected = {
        'status': 'STALE',
        'actions': [
            {
                'name': 'create-project',
                'description': f"Create GCP project '{data['config']['project_id']}'",
                'args': ['create_project']
            }
        ]
    }

    if billing_account_id is not None:
        data['config']['billing_account_id'] = billing_account_id
        expected['actions'].append({
            'name': 'set-billing-account',
            'description': f"Set billing account to '{billing_account_id}'",
            'args': ['set_billing_account']
        })
    if disabled_apis is not None:
        if 'apis' not in data['config']:
            data['config']['apis'] = {}
        data['config']['apis']['disabled'] = disabled_apis
        for api in disabled_apis:
            expected['actions'].append({
                'name': f'disable-api-{api}',
                'description': f"Disable API '{api}'",
                'args': ['disable_api', api]
            })
    if enabled_apis is not None:
        if 'apis' not in data['config']:
            data['config']['apis'] = {}
        data['config']['apis']['enabled'] = enabled_apis
        for api in enabled_apis:
            expected['actions'].append({
                'name': f'enable-api-{api}',
                'description': f"Enable API '{api}'",
                'args': ['enable_api', api]
            })

    project = GcpProject(data=data, gcp_services=MockGcpServices({}, {}, {}))
    if enabled_apis is not None and disabled_apis is not None \
        and ([api for api in disabled_apis if api in enabled_apis]
             or [api for api in enabled_apis if api in disabled_apis]):
        with pytest.raises(Exception, match=r'cannot be both enabled & disabled'):
            project.execute(['state'])
    else:
        project.execute(['state'])
        assert json.loads(capsys.readouterr().out) == expected
