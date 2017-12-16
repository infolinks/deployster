import json
from copy import deepcopy
from pathlib import Path
from typing import Sequence

import pytest
from _pytest.capture import CaptureResult

from dresources import DResource, DAction, DPlug
from mock_external_services import MockExternalServices


@pytest.mark.parametrize("name", ["test"])
@pytest.mark.parametrize("type", ["test-resource", "test/resource", "test/resource:abc"])
@pytest.mark.parametrize("version", ["1", "1.2", "1.2.3"])
@pytest.mark.parametrize("verbose", [True, False])
@pytest.mark.parametrize("workspace", ["./tests/.cache/workspace"])
@pytest.mark.parametrize("config", [{'k1': 'v1', 'k2': 2}, {}, None])
@pytest.mark.parametrize("stale_state", [{'old_k1': 'old_v1', 'old_k2': 1}, {}, None])
def test_new_dresource(name: str,
                       type: str,
                       version: str,
                       verbose: bool,
                       workspace: str,
                       config: dict,
                       stale_state: dict):
    class TestResource(DResource):

        def __init__(self) -> None:
            super().__init__(data=deepcopy({
                'name': name,
                'type': type,
                'version': version,
                'verbose': verbose,
                'workspace': workspace,
                'config': config,
                'staleState': stale_state
            }), svc=MockExternalServices())

        def discover_state(self):
            pass

        def get_actions_for_missing_state(self) -> Sequence[DAction]:
            pass

        def get_actions_for_discovered_state(self, state: dict) -> Sequence[DAction]:
            pass

    resource: TestResource = TestResource()
    assert resource.info.name == name
    assert resource.info.type == type
    assert resource.info.deployster_version == version
    assert resource.info.verbose == verbose
    assert resource.info.workspace == Path(workspace)
    assert resource.info.config == config
    assert resource.info.stale_state == stale_state


def test_abstract_methods_fail():
    class TestResource(DResource):

        def __init__(self) -> None:
            super().__init__(data={
                'name': 'test',
                'type': 'test-resource',
                'version': '1.2.3',
                'verbose': True,
                'workspace': '/workspace',
                'config': {},
                'staleState': {}
            }, svc=MockExternalServices())

        def discover_state(self):
            return super().discover_state()

        def get_actions_for_missing_state(self) -> Sequence[DAction]:
            return super().get_actions_for_missing_state()

        def get_actions_for_discovered_state(self, state: dict) -> Sequence[DAction]:
            return super().get_actions_for_discovered_state(state)

    resource: TestResource = TestResource()
    with pytest.raises(NotImplementedError):
        resource.discover_state()
    with pytest.raises(NotImplementedError):
        resource.get_actions_for_missing_state()
    with pytest.raises(NotImplementedError):
        resource.get_actions_for_discovered_state({})


@pytest.mark.parametrize("plug_name", ["test"])
@pytest.mark.parametrize("container_path", ["/my"])
@pytest.mark.parametrize("optional", [True, False])
@pytest.mark.parametrize("writable", [True, False])
def test_plugs(plug_name: str, container_path: str, optional: bool, writable: bool):
    class TestResource(DResource):

        def __init__(self) -> None:
            super().__init__(data={
                'name': 'test',
                'type': 'test-resource',
                'version': '1.2.3',
                'verbose': True,
                'workspace': '/workspace',
                'config': {},
                'staleState': {}
            }, svc=MockExternalServices())

        def discover_state(self):
            pass

        def get_actions_for_missing_state(self) -> Sequence[DAction]:
            pass

        def get_actions_for_discovered_state(self, state: dict) -> Sequence[DAction]:
            pass

    resource: TestResource = TestResource()
    with pytest.raises(KeyError):
        resource.get_plug(plug_name)
    resource.add_plug(name=plug_name, container_path=container_path, optional=optional, writable=writable)
    plug: DPlug = resource.get_plug(plug_name)
    assert plug.container_path == container_path
    assert plug.optional == optional
    assert plug.writable == writable

    resource.add_plug(name=plug_name + '_',
                      container_path=container_path + '_',
                      optional=not optional,
                      writable=not writable)
    plug_: DPlug = resource.get_plug(plug_name + '_')
    assert plug_.container_path == container_path + '_'
    assert plug_.optional == (not optional)
    assert plug_.writable == (not writable)


def test_default_config_schema():
    class TestResource(DResource):

        def __init__(self) -> None:
            super().__init__(data={
                'name': 'test',
                'type': 'test-resource',
                'version': '1.2.3',
                'verbose': True,
                'workspace': '/workspace',
                'config': {},
                'staleState': {}
            }, svc=MockExternalServices())

        def discover_state(self):
            pass

        def get_actions_for_missing_state(self) -> Sequence[DAction]:
            pass

        def get_actions_for_discovered_state(self, state: dict) -> Sequence[DAction]:
            pass

    resource: TestResource = TestResource()
    assert resource.config_schema == {"type": "object", "additionalProperties": True, "properties": {}}


@pytest.mark.parametrize("plug_name", ["test"])
@pytest.mark.parametrize("plug_container_path", ["/my"])
@pytest.mark.parametrize("plug_optional", [True, False])
@pytest.mark.parametrize("plug_writable", [True, False])
def test_init_action(capsys, plug_name: str, plug_container_path: str, plug_optional: bool, plug_writable: bool):
    class TestResource(DResource):

        def __init__(self) -> None:
            super().__init__(data={
                'name': 'test',
                'type': 'test-resource',
                'version': '1.2.3',
                'verbose': True,
                'workspace': '/workspace',
                'config': {},
                'staleState': {}
            }, svc=MockExternalServices())
            self.config_schema['properties'].update({
                'myProperty': {
                    'type': 'string'
                }
            })
            self.add_plug(name=plug_name,
                          container_path=plug_container_path,
                          optional=plug_optional,
                          writable=plug_writable)

        def discover_state(self):
            pass

        def get_actions_for_missing_state(self) -> Sequence[DAction]:
            pass

        def get_actions_for_discovered_state(self, state: dict) -> Sequence[DAction]:
            pass

    resource: TestResource = TestResource()
    resource.execute(['init'])

    captured: CaptureResult = capsys.readouterr()
    assert json.loads(captured.out) == {
        "plugs": {
            plug_name: {
                'container_path': plug_container_path,
                'optional': plug_optional,
                'writable': plug_writable
            }
        },
        "config_schema": {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "myProperty": {"type": "string"}
            }
        },
        "state_action": {
            "args": ["state"]
        }
    }


@pytest.mark.parametrize("state,missing_state_actions,existing_state_actions,expected", [
    (None,
     [
         {'name': 'a1', 'description': 'A1', 'image': 'a1:t', 'entrypoint': 'a1.py', 'args': ['a11', 'a12', 'a13']},
         {'name': 'a2', 'description': 'A2', 'image': 'a2:t', 'entrypoint': 'a2.py', 'args': ['a21', 'a22', 'a23']}
     ],
     None,
     {
         'status': 'STALE',
         'actions': [
             {'name': 'a1', 'description': 'A1', 'image': 'a1:t', 'entrypoint': 'a1.py', 'args': ['a11', 'a12', 'a13']},
             {'name': 'a2', 'description': 'A2', 'image': 'a2:t', 'entrypoint': 'a2.py', 'args': ['a21', 'a22', 'a23']}
         ]
     }),
    ({'prop1': 'v1', 'prop2': 'v2'},
     None,
     [
         {'name': 'a1', 'description': 'A1', 'image': 'a1:t', 'entrypoint': 'a1.py', 'args': ['a11', 'a12', 'a13']},
         {'name': 'a2', 'description': 'A2', 'image': 'a2:t', 'entrypoint': 'a2.py', 'args': ['a21', 'a22', 'a23']}
     ],
     {
         'status': 'STALE',
         'staleState': {'prop1': 'v1', 'prop2': 'v2'},
         'actions': [
             {'name': 'a1', 'description': 'A1', 'image': 'a1:t', 'entrypoint': 'a1.py', 'args': ['a11', 'a12', 'a13']},
             {'name': 'a2', 'description': 'A2', 'image': 'a2:t', 'entrypoint': 'a2.py', 'args': ['a21', 'a22', 'a23']}
         ]
     }),
    ({'prop1': 'v1', 'prop2': 'v2'},
     None,
     None,
     {
         'status': 'VALID',
         'state': {'prop1': 'v1', 'prop2': 'v2'}
     })
])
def test_state_action(capsys,
                      state: dict,
                      missing_state_actions: Sequence[dict],
                      existing_state_actions: Sequence[dict],
                      expected):
    class TestResource(DResource):

        def __init__(self) -> None:
            super().__init__(data={
                'name': 'test',
                'type': 'test-resource',
                'version': '1.2.3',
                'verbose': True,
                'workspace': '/workspace',
                'config': {},
                'staleState': {}
            }, svc=MockExternalServices())

        def discover_state(self):
            return state

        def get_actions_for_missing_state(self) -> Sequence[DAction]:
            return [DAction(name=a['name'], description=a['description'], image=a['image'],
                            entrypoint=a['entrypoint'], args=a['args'])
                    for a in missing_state_actions or []]

        def get_actions_for_discovered_state(self, state: dict) -> Sequence[DAction]:
            return [DAction(name=a['name'], description=a['description'], image=a['image'],
                            entrypoint=a['entrypoint'], args=a['args'])
                    for a in existing_state_actions or []]

    resource: TestResource = TestResource()
    resource.execute(['state'])

    captured: CaptureResult = capsys.readouterr()
    assert json.loads(captured.out) == expected
