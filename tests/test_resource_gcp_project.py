import json

import pytest

from gcp_project import GcpProject
from mock_gcp_services import MockGcpServices, load_scenarios


@pytest.mark.parametrize("description,actual,config,expected",
                         load_scenarios(scenarios_dir='./tests/scenarios/gcp_project',
                                        scenario_pattern=r'^test_resource_gcp_project_\d+\.json'))
def test_project_state(capsys, description: str, actual: dict, config: dict, expected: dict):
    if description: pass

    mock_gcp_services = MockGcpServices(projects=actual['project'], project_billing_infos=actual['billing'],
                                        project_apis=actual['apis'])
    resource = GcpProject(
        data={
            'name': 'test',
            'type': 'test-resource',
            'version': '1.2.3',
            'verbose': True,
            'workspace': '/workspace',
            'config': config
        },
        gcp_services=mock_gcp_services)

    if 'apis' in config:
        apis = config['apis']
        if 'enabled' in apis and 'disabled' in apis:
            enabled_apis = apis['enabled']
            disabled_apis = apis['disabled']
            if [api for api in disabled_apis if api in enabled_apis] and \
                    [api for api in enabled_apis if api in disabled_apis]:
                with pytest.raises(Exception, match=r'cannot be both enabled & disabled'):
                    resource.execute(['state'])
                return

    resource.execute(['state'])
    state = json.loads(capsys.readouterr().out)
    assert state == expected

    if state['status'] == "STALE":
        for action in state["actions"]:
            resource = GcpProject(
                data={
                    'name': 'test',
                    'type': 'test-resource',
                    'version': '1.2.3',
                    'verbose': True,
                    'workspace': '/workspace',
                    'config': config,
                    'staleState': state['staleState'] if 'staleState' in state else {}
                },
                gcp_services=mock_gcp_services)
            resource.execute(action['args'] if 'args' in action else [])
