import json

import jsonschema
import pytest

from k8s import K8sResource
from manifest import Resource
from mock_k8s_services import MockK8sServices
from scenario_util import load_scenarios


@pytest.mark.parametrize("description,actual,config,expected",
                         load_scenarios(scenarios_dir='./tests/scenarios/k8s',
                                        scenario_pattern=r'^test_resource_k8s_\d+\.json'))
def test_k8s(capsys, description: str, actual: dict, config: dict, expected: dict):
    if description: pass

    mock_k8s_services = MockK8sServices(objects=actual['objects'])

    # test "init" action
    K8sResource(data={'name': 'test', 'type': 'test', 'version': '1.2.3', 'verbose': True,
                      'workspace': '/workspace', 'config': config},
                k8s_services=mock_k8s_services).execute(['init'])
    init_result = json.loads(capsys.readouterr().out)
    jsonschema.validate(init_result, Resource.init_action_stdout_schema)
    if 'config_schema' in init_result:
        jsonschema.validate(config, init_result['config_schema'])

    # test "state" action
    resource = K8sResource(data={'name': 'test', 'type': 'test', 'version': '1.2.3', 'verbose': True,
                                 'workspace': '/workspace', 'config': config},
                           k8s_services=mock_k8s_services)
    if 'exception' in expected:
        with pytest.raises(eval(expected['exception']), match=expected["match"] if 'match' in expected else r'.*'):
            resource.execute(['state'])
    else:
        resource.execute(['state'])
        state = json.loads(capsys.readouterr().out)
        assert state == expected
        if state['status'] == "STALE":
            for action in state["actions"]:
                K8sResource(data={'name': 'test', 'type': 'test', 'version': '1.2.3', 'verbose': True,
                                  'workspace': '/workspace', 'config': config,
                                  'staleState': state['staleState'] if 'staleState' in state else {}},
                            k8s_services=mock_k8s_services).execute(action['args'] if 'args' in action else [])