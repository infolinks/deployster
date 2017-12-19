import json
import time

import jsonschema
import pytest

from external_services import ExternalServices
from k8s import K8sResource
from manifest import Resource
from mock_external_services import MockExternalServices


@pytest.mark.parametrize("timeout_ms", [100, 500, 700])
@pytest.mark.parametrize("timeout_interval_ms", [100, 300, 600])
@pytest.mark.parametrize("time_until_available_ms", [0, 10, 500, 600])
def test_k8s_resource_check_availability(capsys, timeout_ms, timeout_interval_ms, time_until_available_ms):
    class MockK8sResource(K8sResource):

        def __init__(self, time_until_available_ms: int, data: dict, svc: ExternalServices) -> None:
            super().__init__(data, svc)
            self._time_until_available_ms: int = time_until_available_ms
            self._creation_time_ms: int = int(round(time.time() * 1000))

        def is_available(self, state: dict) -> bool:
            now_ms: int = int(round(time.time() * 1000))
            return now_ms - self._creation_time_ms >= self._time_until_available_ms

    data: dict = {
        'name': 'test',
        'type': 'test-resource',
        'version': '1.2.3',
        'verbose': True,
        'workspace': '/workspace',
        'config': {
            "timeout_ms": timeout_ms,
            "timeout_interval_ms": timeout_interval_ms,
            "manifest": {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {
                    "name": "test"
                }
            }
        }
    }

    if timeout_interval_ms >= timeout_ms:
        with pytest.raises(Exception, match=r"timeout interval \(\d+(.\d+)?\) cannot be greater than "
                                            r"or equal to total timeout \(\d+(.\d+)?\) duration"):
            MockK8sResource(time_until_available_ms=time_until_available_ms,
                            data=data,
                            svc=MockExternalServices(k8s_objects={})).execute(["state"])
    else:
        resource = MockK8sResource(time_until_available_ms=time_until_available_ms,
                                   data=data,
                                   svc=MockExternalServices(k8s_objects={}))

        resource.execute(["init"])
        init_result = json.loads(capsys.readouterr().out)
        jsonschema.validate(init_result, Resource.init_action_stdout_schema)

        # if the "init" action provided a "config_schema", validate the scenario resource configuration to it
        if 'config_schema' in init_result:
            jsonschema.validate(resource.info.config, init_result['config_schema'])

        time_needed: int = 0
        while time_needed < time_until_available_ms:
            time_needed += timeout_interval_ms

        if time_needed > timeout_ms:
            with pytest.raises(TimeoutError, match=f"timed out waiting"):
                resource.check_availability()
        else:
            resource.check_availability()
