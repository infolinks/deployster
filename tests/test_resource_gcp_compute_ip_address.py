import json

import jsonschema
import pytest

from gcp_compute_ip_address import GcpIpAddress
from manifest import Resource
from mock_gcp_services import MockGcpServices
from scenario_util import load_scenarios


@pytest.mark.parametrize("description,actual,config,expected",
                         load_scenarios(scenarios_dir='./tests/scenarios/gcp_compute_ip_address',
                                        scenario_pattern=r'^test_resource_gcp_compute_ip_address_\d+\.json'))
def test_compute_ip_address(capsys, description: str, actual: dict, config: dict, expected: dict):
    if description: pass

    mock_gcp_services = MockGcpServices(compute_regional_ip_addresses=actual["compute_regional_ip_addresses"],
                                        compute_global_ip_addresses=actual["compute_global_ip_addresses"])

    # test "init" action
    GcpIpAddress(data={'name': 'test', 'type': 'test', 'version': '1.2.3', 'verbose': True,
                       'workspace': '/workspace', 'config': config},
                 gcp_services=mock_gcp_services).execute(['init'])
    init_result = json.loads(capsys.readouterr().out)
    jsonschema.validate(init_result, Resource.init_action_stdout_schema)
    if 'config_schema' in init_result:
        jsonschema.validate(config, init_result['config_schema'])

    # test "state" action
    resource = GcpIpAddress(data={'name': 'test', 'type': 'test', 'version': '1.2.3', 'verbose': True,
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
                GcpIpAddress(data={'name': 'test', 'type': 'test', 'version': '1.2.3', 'verbose': True,
                                   'workspace': '/workspace', 'config': config,
                                   'staleState': state['staleState'] if 'staleState' in state else {}},
                             gcp_services=mock_gcp_services).execute(action['args'] if 'args' in action else [])
