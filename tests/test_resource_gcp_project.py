import json

import jsonschema
import pytest

from gcp_project import GcpProject
from manifest import Resource
from mock_gcp_services import MockGcpServices, load_scenarios


@pytest.mark.parametrize("description,actual,config,expected",
                         load_scenarios(scenarios_dir='./tests/scenarios/gcp_project',
                                        scenario_pattern=r'^test_resource_gcp_project_\d+\.json'))
def test_project(capsys, description: str, actual: dict, config: dict, expected: dict):
    if description: pass

    mock_gcp_services = MockGcpServices(projects=actual['project'], project_billing_infos=actual['billing'],
                                        project_apis=actual['apis'])

    # test "init" action
    GcpProject(data={'name': 'test', 'type': 'test', 'version': '1.2.3', 'verbose': True,
                     'workspace': '/workspace', 'config': config},
               gcp_services=mock_gcp_services).execute(['init'])
    init_result = json.loads(capsys.readouterr().out)
    jsonschema.validate(init_result, Resource.init_action_stdout_schema)
    if 'config_schema' in init_result:
        jsonschema.validate(config, init_result['config_schema'])

    # test "state" action
    resource = GcpProject(data={'name': 'test', 'type': 'test', 'version': '1.2.3', 'verbose': True,
                                'workspace': '/workspace', 'config': config},
                          gcp_services=mock_gcp_services)
    if 'exception' in expected:
        with pytest.raises(eval(expected['exception']), match=expected["match"] if 'match' in expected else r'.*'):
            resource.execute(['state'])
    else:
        resource.execute(['state'])
        state = json.loads(capsys.readouterr().out)
        assert state == expected
        if state['status'] == "STALE":
            for action in state["actions"]:
                GcpProject(data={'name': 'test', 'type': 'test', 'version': '1.2.3', 'verbose': True,
                                 'workspace': '/workspace', 'config': config,
                                 'staleState': state['staleState'] if 'staleState' in state else {}},
                           gcp_services=mock_gcp_services).execute(action['args'] if 'args' in action else [])
