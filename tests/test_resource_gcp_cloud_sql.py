import json

import pytest

from gcp_cloud_sql import GcpCloudSql, _translate_day_name_to_number
from mock_gcp_services import MockGcpServices, load_scenarios


@pytest.mark.parametrize("day_name,expected", [
    ("Monday", 1),
    ("Tuesday", 2),
    ("Wednesday", 3),
    ("Thursday", 4),
    ("Friday", 5),
    ("Saturday", 6),
    ("Sunday", 7),
    ("Unknown", None),
])
def test_week_day_translation(day_name: str, expected: int):
    if expected is None:
        with pytest.raises(Exception, match='unknown week-day encountered'):
            _translate_day_name_to_number(day_name)
    else:
        assert _translate_day_name_to_number(day_name) == expected


@pytest.mark.parametrize("description,actual,config,expected",
                         load_scenarios(scenarios_dir='./tests/scenarios/gcp_cloud_sql',
                                        scenario_pattern=r'^test_resource_gcp_cloud_sql_\d+\.json'))
def test_cloud_sql_state(capsys, description: str, actual: dict, config: dict, expected: dict):
    if description: pass

    mock_gcp_services = MockGcpServices(project_apis=actual["project_apis"], sql_tiers=actual['tiers'],
                                        sql_flags=actual['flags'], sql_instances=actual['instances'],
                                        sql_execution_results=actual['sql_results'])
    resource = GcpCloudSql(
        data={
            'name': 'test',
            'type': 'test-resource',
            'version': '1.2.3',
            'verbose': True,
            'workspace': '/workspace',
            'config': config
        },
        gcp_services=mock_gcp_services)

    if 'exception' in expected:
        with pytest.raises(eval(expected['exception'])):
            resource.execute(['state'])
    else:
        resource.execute(['state'])
        state = json.loads(capsys.readouterr().out)
        assert state == expected
        if state['status'] == "STALE":
            for action in state["actions"]:
                resource = GcpCloudSql(
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
