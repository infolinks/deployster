import json
from typing import Sequence, Union, Mapping

import pytest

from gcp_project import GcpProject
from gcp_services import GcpServices
from util import UserError


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


@pytest.mark.parametrize("actual,config,expected", [
    (
            {
                'project': {
                    'prj': {"projectId": 'prj', "name": 'prj', 'parent': {'type': 'organization', 'id': '123'}}
                },
                'billing': {
                    'prj': {'billingAccountName': f'billingAccounts/ABC123'}
                },
                'apis': {
                    'prj': ["api1"]
                }
            },
            {
                "project_id": 'prj',
                "organization_id": 123,
                "billing_account_id": "ABC123",
                "apis": {"enabled": ["api1"], "disabled": ["api2", "api3"]}
            },
            {
                "status": "VALID",
                "state": {
                    "apis": {"enabled": ["api1"]},
                    "billing_account_id": "ABC123",
                    "name": "prj",
                    "parent": {"type": "organization", "id": "123"},
                    "projectId": "prj"
                }
            }
    ),
    (
            {
                'project': {
                    'prj': {"projectId": 'prj', "name": 'prj', 'parent': {'type': 'organization', 'id': '123'}}
                },
                'billing': {
                    'prj': {'billingAccountName': f'billingAccounts/ABC123'}
                },
                'apis': {
                    'prj': ["api1"]
                }
            },
            {
                "project_id": 'prj',
                "organization_id": 1234,
                "billing_account_id": "ABC123",
                "apis": {"enabled": ["api1"], "disabled": ["api2", "api3"]}
            },
            {
                "status": "STALE",
                "staleState": {
                    "apis": {"enabled": ["api1"]},
                    "billing_account_id": "ABC123",
                    "name": "prj",
                    "parent": {"type": "organization", "id": "123"},
                    "projectId": "prj"
                },
                "actions": [{'name': 'set-parent',
                             'description': f"Set organization to '1234'",
                             'args': ['set_parent']}]
            }
    ),
    (
            {
                'project': {
                    'prj2': {"projectId": 'prj', "name": 'prj', 'parent': {'type': 'organization', 'id': '123'}}
                },
                'billing': {
                    'prj2': {'billingAccountName': f'billingAccounts/ABC123'}
                },
                'apis': {
                    'prj2': ["api1"]
                }
            },
            {
                "project_id": 'prj',
                "organization_id": 1234,
                "billing_account_id": "ABC123",
                "apis": {"enabled": ["api1"], "disabled": ["api2", "api3"]}
            },
            {
                "status": "STALE",
                "actions": [
                    {
                        'name': 'create-project',
                        'description': f"Create GCP project 'prj'",
                        'args': ['create_project']
                    },
                    {
                        'name': 'set-billing-account',
                        'description': "Set billing account to 'ABC123'",
                        'args': ['set_billing_account']
                    },
                    {
                        'name': 'disable-api-api2',
                        'description': "Disable API 'api2'",
                        'args': ['disable_api', 'api2']
                    },
                    {
                        'name': 'disable-api-api3',
                        'description': "Disable API 'api3'",
                        'args': ['disable_api', 'api3']
                    },
                    {
                        'name': 'enable-api-api1',
                        'description': "Enable API 'api1'",
                        'args': ['enable_api', 'api1']
                    }
                ]
            }
    )
])
def test_project_state(capsys, actual: dict, config: dict, expected: dict):
    project = GcpProject(
        data={
            'name': 'test',
            'type': 'test-resource',
            'version': '1.2.3',
            'verbose': True,
            'workspace': '/workspace',
            'config': config
        },
        gcp_services=MockGcpServices(projects=actual['project'],
                                     project_billing_infos=actual['billing'],
                                     project_apis=actual['apis']))

    if 'apis' in config:
        apis = config['apis']
        if 'enabled' in apis and 'disabled' in apis:
            enabled_apis = apis['enabled']
            disabled_apis = apis['disabled']
            if [api for api in disabled_apis if api in enabled_apis] and \
                    [api for api in enabled_apis if api in disabled_apis]:
                with pytest.raises(UserError, match=r'cannot be both enabled & disabled'):
                    project.execute(['state'])
                    return

    project.execute(['state'])
    assert json.loads(capsys.readouterr().out) == expected
