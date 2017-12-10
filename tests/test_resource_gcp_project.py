import json

import pytest

from gcp_project import GcpProject
from mock_gcp_services import MockGcpServices, load_scenarios


@pytest.mark.parametrize("actual,config,expected", load_scenarios(r'^test_resource_gcp_project_\d+\.json'))
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
                with pytest.raises(Exception, match=r'cannot be both enabled & disabled'):
                    project.execute(['state'])
                return

    project.execute(['state'])
    assert json.loads(capsys.readouterr().out) == expected
