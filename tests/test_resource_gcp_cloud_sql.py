import json

import pytest

from gcp_cloud_sql import GcpCloudSql
from mock_gcp_services import MockGcpServices, load_scenarios


@pytest.mark.parametrize("actual,config,expected",
                         load_scenarios(scenarios_dir='./tests/scenarios/gcp_cloud_sql',
                                        scenario_pattern=r'^test_resource_gcp_cloud_sql_\d+\.json'))
def test_cloud_sql_state(capsys, actual: dict, config: dict, expected: dict):
    resource = GcpCloudSql(
        data={
            'name': 'test',
            'type': 'test-resource',
            'version': '1.2.3',
            'verbose': True,
            'workspace': '/workspace',
            'config': config
        },
        gcp_services=MockGcpServices(project_apis=actual["project_apis"],
                                     sql_tiers=actual['tiers'],
                                     sql_flags=actual['flags'],
                                     sql_instances=actual['instances']))

    resource.execute(['state'])
    assert json.loads(capsys.readouterr().out) == expected