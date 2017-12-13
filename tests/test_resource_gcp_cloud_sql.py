import json

import jsonschema
import pytest

from gcp_cloud_sql import GcpCloudSql, _translate_day_name_to_number, Condition, ConditionFactory
from gcp_services import SqlExecutor
from manifest import Resource
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


def test_condition_evaluate_is_abstract():
    with pytest.raises(NotImplementedError):
        class TestCondition(Condition):

            def evaluate(self, sql_executor: SqlExecutor) -> bool:
                return super().evaluate(sql_executor)

        TestCondition(ConditionFactory(), {}).evaluate(SqlExecutor(MockGcpServices()))


@pytest.mark.parametrize("description,actual,config,expected",
                         load_scenarios(scenarios_dir='./tests/scenarios/gcp_cloud_sql',
                                        scenario_pattern=r'^test_resource_gcp_cloud_sql_\d+\.json'))
def test_cloud_sql(capsys, description: str, actual: dict, config: dict, expected: dict):
    if description: pass

    mock_gcp_services = MockGcpServices(project_apis=actual["project_apis"], sql_tiers=actual['tiers'],
                                        sql_flags=actual['flags'], sql_instances=actual['instances'],
                                        sql_execution_results=actual['sql_results'])

    # test "init" action
    GcpCloudSql(data={'name': 'test', 'type': 'test', 'version': '1.2.3', 'verbose': True,
                      'workspace': '/workspace', 'config': config},
                gcp_services=mock_gcp_services).execute(['init'])
    init_result = json.loads(capsys.readouterr().out)
    jsonschema.validate(init_result, Resource.init_action_stdout_schema)
    if 'config_schema' in init_result:
        jsonschema.validate(config, init_result['config_schema'])

    # test "state" action
    resource = GcpCloudSql(data={'name': 'test', 'type': 'test', 'version': '1.2.3', 'verbose': True,
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
                GcpCloudSql(data={'name': 'test', 'type': 'test', 'version': '1.2.3', 'verbose': True,
                                  'workspace': '/workspace', 'config': config,
                                  'staleState': state['staleState'] if 'staleState' in state else {}},
                            gcp_services=mock_gcp_services).execute(action['args'] if 'args' in action else [])


def test_execution_of_unknown_script_bundle():
    resource = GcpCloudSql(
        data={
            'name': 'test',
            'type': 'test-resource',
            'version': '1.2.3',
            'verbose': True,
            'workspace': '/workspace',
            'config': {
                "project_id": "prj",
                "zone": "europe-west1-a",
                "name": "sql1",
                "machine-type": "db-1",
                "root-password": "abcdefg",
                "scripts": [
                    {
                        "name": "my-script",
                        "paths": ["./tests/scenarios/gcp_cloud_sql/script-does-not-exist-errrrrrrrr.sql"],
                        "when": []
                    }
                ]
            }
        },
        gcp_services=MockGcpServices(project_apis={},
                                     sql_tiers={},
                                     sql_flags={},
                                     sql_instances={}))

    with pytest.raises(Exception):
        resource.execute(['execute_scripts', 'unknown-script'])
