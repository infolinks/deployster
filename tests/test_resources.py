import importlib
import json
import os
import re
from copy import deepcopy
from typing import Sequence, Tuple, MutableSequence, Callable

import jsonschema
import pytest
import yaml

import util
from dresources import DResource
from external_services import ExternalServices
from manifest import Resource
from mock_external_services import MockExternalServices


def find_scenarios(scenario_pattern: str) -> Sequence[Tuple[str, dict, dict, dict]]:
    scenarios: MutableSequence[Tuple[str, dict, dict, dict]] = []
    for dir_name, subdir_list, file_list in os.walk('./tests/scenarios'):
        for file_name in file_list:
            full_file_name = os.path.join(dir_name, file_name)
            if not re.match(scenario_pattern, full_file_name):
                continue

            file_description = full_file_name[0:-5]
            try:
                with open(full_file_name, 'r') as f:
                    if file_name.endswith('.yaml'):
                        content: dict = yaml.load(f)
                    elif file_name.endswith('.json'):
                        content: dict = json.loads(f.read())
                    else:
                        raise Exception(f"unsupported scenarios file: {full_file_name}")

                default_resource: dict = content["default_resource"] if "default_resource" in content else {}
                default_expected: dict = content["default_expected"] if "default_expected" in content else {}
                file_mock: dict = content["mock"] if "mock" in content else {}
                for scenario in content["scenarios"]:
                    file_mock_copy: dict = deepcopy(file_mock)
                    scenarios.append((
                        file_description + '_' + (scenario["description"] if "description" in scenario else "unknown"),
                        util.merge(file_mock_copy, scenario["mock"]) if "mock" in scenario else file_mock_copy,
                        util.merge(deepcopy(default_resource), scenario["resource"] if "resource" in scenario else {}),
                        util.merge(deepcopy(default_expected), scenario["expected"])
                    ))
            except Exception as e:
                raise Exception(f"failed creating scenario from '{full_file_name}'") from e
    return scenarios


def create_resource(svc: MockExternalServices,
                    resource: dict,
                    include_config: bool = False,
                    extra_data: dict = None) -> DResource:
    """Creates a resource instance (subclass of DResource)."""
    module = importlib.import_module(resource["module"])
    resource_type: Callable[[dict, ExternalServices], DResource] = getattr(module, resource["class"])
    data = {"name": resource["name"] if 'name' in resource else 'test',
            "type": resource["class"],
            "version": resource["version"] if "version" in resource else "0.0.0",
            "verbose": resource["verbose"] if 'verbose' in resource else True,
            "workspace": "/workspace"}
    if include_config:
        data.update({"config": resource["config"]})
    if extra_data is not None:
        data.update(extra_data)
    return resource_type(data, svc)


@pytest.mark.parametrize("description,mock,resource,expected",
                         find_scenarios(scenario_pattern=r'.*[a-zA-Z]\.(json|yaml)$'))
def test_resources(capsys, description: str, mock: dict, resource: dict, expected: dict):
    if description: pass
    mock_services = MockExternalServices(
        gcloud_access_token='random-string-here',
        gcp_projects=mock["gcp_projects"] if "gcp_projects" in mock else {},
        gcp_project_billing_infos=mock[
            "gcp_project_billing_accounts"] if "gcp_project_billing_accounts" in mock else {},
        gcp_project_apis=mock["gcp_project_apis"] if "gcp_project_apis" in mock else {},
        gcp_iam_service_accounts=mock["gcp_iam_service_accounts"] if "gcp_iam_service_accounts" in mock else {},
        gcp_iam_policies=mock["gcp_iam_policies"] if "gcp_iam_policies" in mock else {},
        gcp_sql_tiers=mock["gcp_sql_tiers"] if "gcp_sql_tiers" in mock else {},
        gcp_sql_flags=mock["gcp_sql_flags"] if "gcp_sql_flags" in mock else {},
        gcp_sql_instances=mock["gcp_sql_instances"] if "gcp_sql_instances" in mock else {},
        gcp_sql_execution_results=mock["gcp_sql_execution_results"] if "gcp_sql_execution_results" in mock else {},
        gcp_sql_users=mock["gcp_sql_users"] if "gcp_sql_users" in mock else {},
        gke_clusters=mock["gke_clusters"] if "gke_clusters" in mock else {},
        gke_server_config=mock["gke_server_config"] if "gke_server_config" in mock else {},
        gcp_compute_regional_ip_addresses=mock[
            "gcp_compute_regional_ip_addresses"] if "gcp_compute_regional_ip_addresses" in mock else {},
        gcp_compute_global_ip_addresses=mock[
            "gcp_compute_global_ip_addresses"] if "gcp_compute_global_ip_addresses" in mock else {},
        k8s_objects=mock["k8s_objects"] if "k8s_objects" in mock else {},
        k8s_create_times=mock["k8s_create_times"] if "k8s_create_times" in mock else {})

    # TODO: verify mock calls (eg. verify that a cluster was indeed created by calling the mock, with the right values)

    # invoke the "init" action, and read its result from stdout
    create_resource(svc=mock_services, resource=resource).execute(['init'])
    init_result = json.loads(capsys.readouterr().out)
    jsonschema.validate(init_result, Resource.init_action_stdout_schema)

    # if the "init" action provided a "config_schema", validate the scenario resource configuration to it
    if 'config_schema' in init_result:
        jsonschema.validate(resource["config"], init_result['config_schema'])

    # test "state" action, and read its result from stdout
    if 'exception' in expected:
        with pytest.raises(eval(expected['exception']), match=expected["match"] if 'match' in expected else r'.*'):
            create_resource(svc=mock_services, resource=resource, include_config=True).execute(['state'])
    else:
        create_resource(svc=mock_services, resource=resource, include_config=True).execute(['state'])
        state = json.loads(capsys.readouterr().out)
        assert state == expected

        # if "state" returned "STALE" status, also execute its list of specified actions
        if state['status'] == "STALE":
            for action in state["actions"]:
                extra_data: dict = {'staleState': state['staleState'] if 'staleState' in state else {}}
                args = action['args'] if 'args' in action else []
                create_resource(svc=mock_services,
                                resource=resource,
                                include_config=True,
                                extra_data=extra_data).execute(args)
