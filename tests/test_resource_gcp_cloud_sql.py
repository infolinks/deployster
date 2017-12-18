import pytest

from external_services import SqlExecutor
# noinspection PyProtectedMember
from gcp_cloud_sql import GcpCloudSql, _translate_day_name_to_number, Condition, ConditionFactory
from mock_external_services import MockExternalServices


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

        TestCondition(ConditionFactory(), {}).evaluate(SqlExecutor(MockExternalServices()))


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
        svc=MockExternalServices())

    with pytest.raises(Exception):
        resource.execute(['execute_scripts', 'unknown-script'])
