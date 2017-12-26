import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Sequence, Tuple, MutableSequence, Mapping

import pytest
import yaml

from context import Context
from manifest import Action, Manifest, Resource, ResourceStatus
from manifest import Plug
from mock_external_services import MockDockerInvoker
from util import UserError


@pytest.mark.parametrize("work_dir", ["/unknown/file", "./tests/.cache/action1"])
@pytest.mark.parametrize("name", [None, "", "action"])
@pytest.mark.parametrize("description", [None, "", "desssscriippttion"])
@pytest.mark.parametrize("image", [None, "", "immmaage"])
@pytest.mark.parametrize("entrypoint", [None, "", "ennntrrrypopiint"])
@pytest.mark.parametrize("args", [None, [], ["1"], ["1", "2"], ["1", "", ""]])
def test_action(work_dir: str, name: str, description: str, image: str, entrypoint: str, args: Sequence[str]):
    action: Action = Action(work_dir=Path(work_dir),
                            name=name,
                            description=description,
                            image=image,
                            entrypoint=entrypoint,
                            args=args)
    assert action.work_dir == Path(work_dir).absolute()
    assert action.name == name
    assert action.description == description
    assert action.image == image
    assert action.entrypoint == entrypoint
    assert action.args == (args if args is not None else [])


@pytest.mark.parametrize("name", ["", "my_plug"])
@pytest.mark.parametrize("path", ["", "/a/b/c"])
@pytest.mark.parametrize("readonly", [True, False])
@pytest.mark.parametrize("allowed_resource_names,allowed_resource_types,resource_name,resource_type,expect_allowed", [
    ([], [], "vm01", "vm:1.0.0", True),
    ([".*"], [], "vm01", "vm:1.0.0", True),
    ([], [".*"], "vm01", "vm:1.0.0", True),
    ([".*"], [".*"], "vm01", "vm:1.0.0", True),
    (["abc"], [], "vm01", "vm:1.0.0", False),
    ([], ["abc"], "vm01", "vm:1.0.0", False),
    (["abc"], ["abc"], "vm01", "vm:1.0.0", False),
    (["abc"], [".*"], "vm01", "vm:1.0.0", True),
    ([".*"], ["abc"], "vm01", "vm:1.0.0", True),
    (["abc", ".*"], [], "vm01", "vm:1.0.0", True),
    ([], ["abc", ".*"], "vm01", "vm:1.0.0", True),
    (["abc", "abc.*"], [], "vm01", "vm:1.0.0", False),
    ([], ["abc", "abc.*"], "vm01", "vm:1.0.0", False)
])
def test_plug(name: str,
              path: str,
              readonly: bool,
              allowed_resource_names: Sequence[str],
              allowed_resource_types: Sequence[str],
              resource_name: str,
              resource_type: str,
              expect_allowed: bool):
    plug: Plug = Plug(name=name,
                      path=path,
                      readonly=readonly,
                      allowed_resource_names=allowed_resource_names,
                      allowed_resource_types=allowed_resource_types)
    assert plug.name == name
    assert plug.path == Path(path).absolute()
    assert plug.readonly == readonly
    assert plug.resource_name_patterns == allowed_resource_names
    assert plug.resource_type_patterns == allowed_resource_types
    assert plug.allowed_for(resource_name, resource_type) == expect_allowed


class MockResource(Resource):

    def __init__(self,
                 manifest: 'Manifest',
                 name: str,
                 type: str,
                 readonly: bool,
                 config: dict = None,
                 dependencies: Mapping[str, 'Resource'] = None) -> None:
        super().__init__(manifest, name, type, readonly, config, dependencies)

    def initialize(self) -> None:
        pass

    def execute(self) -> None:
        super().execute()


def find_scenarios() -> Sequence[Tuple[str, Path, dict, Sequence[Path]]]:
    scenarios: MutableSequence[Tuple[str, Path, dict, Sequence[Path]]] = []
    root: Path = Path('./tests/manifest_scenarios').absolute()
    for scenario_dir in root.iterdir():
        if scenario_dir.is_dir():
            scenario_file: Path = scenario_dir / 'scenario.yaml'
            if scenario_file.exists():
                with scenario_file.open('r') as sf:
                    scenario: dict = yaml.load(sf)
                scenarios.append((
                    scenario_dir.name,
                    scenario_dir,
                    scenario,
                    [scenario_dir / file for file in scenario_dir.iterdir() if file.name != 'scenario.yaml']
                ))
    return scenarios


@pytest.mark.parametrize("description,dir,scenario,manifest_files", find_scenarios())
def test_manifest(capsys, description: str, dir: Path, scenario: dict, manifest_files: Sequence[Path]):
    context: Context = Context(version_file_path='./tests/test_version', env={
        "CONF_DIR": str(dir.absolute() / 'conf'),
        "WORKSPACE_DIR": str(dir.absolute()),
        "WORK_DIR": str(Path('./tests/.cache/manifest_scenarios') / description)
    })
    context.add_variable("k1", "v1")
    context.add_variable("k2", "v2")

    def create_manifest():
        manifest: Manifest = Manifest(context=context, manifest_files=manifest_files, resource_factory=MockResource)
        assert manifest.manifest_files == manifest_files
        assert manifest.context == context
        return manifest

    if 'expected' not in scenario:
        create_manifest()
    else:
        expected: dict = scenario['expected']
        if 'exception' in expected:
            with pytest.raises(eval(expected['exception']), match=expected["match"] if 'match' in expected else r'.*'):
                create_manifest()
        else:
            manifest: Manifest = create_manifest()
            manifest.display_plugs()
            output: str = capsys.readouterr().out
            assert output.find('Plugs:') >= 0

            if 'plugs' in expected:
                assert manifest.plugs == {name: manifest.plug(name) for name in expected['plugs'].keys()}
                for plug_name, expected_plug in expected['plugs'].items():
                    plug: Plug = manifest.plug(plug_name)
                    if 'name' in expected_plug: assert plug.name == expected_plug['name']
                    if 'path' in expected_plug: assert plug.path == Path(expected_plug['path']).absolute()
                    if 'readonly' in expected_plug: assert plug.readonly == expected_plug['readonly']
                    if 'resource_name_patterns' in expected_plug:
                        assert plug.resource_name_patterns == expected_plug['resource_name_patterns']
                    if 'resource_type_patterns' in expected_plug:
                        assert plug.resource_type_patterns == expected_plug['resource_type_patterns']
            if 'resources' in expected:
                assert manifest.resources == {name: manifest.resource(name) for name in expected['resources'].keys()}
                for resource_name, expected_resource in expected['resources'].items():
                    resource: Resource = manifest.resource(resource_name)
                    if 'readonly' in expected_resource: assert resource.readonly == expected_resource['readonly']
                    if 'name' in expected_resource: assert resource.name == expected_resource['name']
                    if 'type' in expected_resource: assert resource.type == expected_resource['type']
                    if 'config' in expected_resource: assert resource.config == expected_resource['config']
                    assert resource.status is None
                    assert resource.state is None
                    if 'dependencies' in expected_resource:
                        expected_dependencies: Mapping[str, Resource] = \
                            {dep_name: manifest.resource(resource_name)
                             for dep_name, resource_name in expected_resource['dependencies'].items()}
                        assert resource.dependencies == expected_dependencies


def test_resource_initialize(capsys):
    scenario_dir: Path = Path('./tests/.cache/manifest_scenarios/test_resource_initialize')
    os.makedirs(str(scenario_dir), exist_ok=True)
    scenario_file: Path = scenario_dir / 'manifest.yaml'
    with scenario_file.open('w') as f:
        f.write(yaml.dump({
            'plugs': {
                'writable_plug': {'path': str(scenario_dir / 'p1'), 'read_only': False},
                'readonly_plug': {'path': str(scenario_dir / 'p2'), 'read_only': True},
                'restricted_plug': {'path': str(scenario_dir / 'p3'), 'resource_names': ['^rX$']}
            },
            'resources': {
                'r1': {'type': 'r1:1'}
            }
        }))

    context: Context = Context(version_file_path='./tests/test_version', env={
        "CONF_DIR": scenario_dir / 'conf',
        "WORKSPACE_DIR": scenario_dir / 'workspace',
        "WORK_DIR": scenario_dir / 'work'
    })
    context.add_variable("k1", "v1")
    context.add_variable("k2", "v2")
    manifest: Manifest = Manifest(context=context, manifest_files=[scenario_file])
    resource: Resource = manifest.resource('r1')

    # test init action returning "-1"
    resource._docker_invoker = MockDockerInvoker(return_code=-1, stderr='ERROR', stdout='ERROR')
    with pytest.raises(UserError, match='Docker command terminated with exit code #-1'):
        resource.initialize()

    # test init action returning empty JSON
    resource._docker_invoker = MockDockerInvoker(return_code=0, stderr='', stdout=json.dumps({}))
    with pytest.raises(UserError, match='initialization result failed validation'):
        resource.initialize()

    # test init action result empty state action
    resource._docker_invoker = MockDockerInvoker(return_code=0, stderr='', stdout=json.dumps({
        'config_schema': {'type': 'object', 'additionalProperties': False},
        'state_action': {}
    }))
    with pytest.raises(UserError, match='state action must not equal the default \'init\' action'):
        resource.initialize()

    # test init action result standard state action
    init_result: dict = {
        'config_schema': {'type': 'object', 'additionalProperties': False},
        'state_action': {'args': ['state']}
    }
    resource._docker_invoker = MockDockerInvoker(return_code=0, stderr='', stdout=json.dumps(init_result))
    resource.initialize()
    assert resource._config_schema == deepcopy(init_result['config_schema'])

    # test init action result requests optionally a missing plug
    init_result: dict = {
        'plugs': {'p0': {'container_path': '/some/where', 'optional': True}},
        'config_schema': {'type': 'object', 'additionalProperties': True},
        'state_action': {'args': ['state']}
    }
    resource._docker_invoker = MockDockerInvoker(return_code=0, stderr='', stdout=json.dumps(init_result))
    resource.initialize()
    output: str = capsys.readouterr().out
    assert output.find('Optional plug \'p0\' does not exist (skipped)') >= 0
    assert resource._plugs == {}

    # test init action result requires missing plug
    init_result: dict = {
        'plugs': {'p0': {'container_path': '/some/where', 'optional': False}},
        'config_schema': {'type': 'object', 'additionalProperties': True},
        'state_action': {'args': ['state']}
    }
    resource._docker_invoker = MockDockerInvoker(return_code=0, stderr='', stdout=json.dumps(init_result))
    with pytest.raises(UserError, match=f"plug \'p0\' required by \'r1\' does not exist"):
        resource.initialize()

    # test init action result requests optionally a restricted plug
    init_result: dict = {
        'plugs': {'restricted_plug': {'container_path': '/some/where', 'optional': True}},
        'config_schema': {'type': 'object', 'additionalProperties': True},
        'state_action': {'args': ['state']}
    }
    resource._docker_invoker = MockDockerInvoker(return_code=0, stderr='', stdout=json.dumps(init_result))
    resource.initialize()
    output: str = capsys.readouterr().out
    assert output.find('Optional plug \'restricted_plug\' is not allowed for this resource (skipped)') >= 0
    assert resource._plugs == {}

    # test init action result requires a restricted plug
    init_result: dict = {
        'plugs': {'restricted_plug': {'container_path': '/some/where', 'optional': False}},
        'config_schema': {'type': 'object', 'additionalProperties': True},
        'state_action': {'args': ['state']}
    }
    resource._docker_invoker = MockDockerInvoker(return_code=0, stderr='', stdout=json.dumps(init_result))
    with pytest.raises(UserError, match=f"plug \'restricted_plug\' required by \'r1\' is not allowed for it"):
        resource.initialize()

    # test init action result requests optionally a readonly plug as writable
    init_result: dict = {
        'plugs': {'readonly_plug': {'container_path': '/some/where', 'optional': True, 'writable': True}},
        'config_schema': {'type': 'object', 'additionalProperties': True},
        'state_action': {'args': ['state']}
    }
    resource._docker_invoker = MockDockerInvoker(return_code=0, stderr='', stdout=json.dumps(init_result))
    resource.initialize()
    output: str = capsys.readouterr().out
    assert output.find('Optional plug \'readonly_plug\' is readonly, but requested with write access (denied)') >= 0
    assert resource._plugs == {}

    # test init action result requires a readonly plug as writable
    init_result: dict = {
        'plugs': {'readonly_plug': {'container_path': '/some/where', 'optional': False, 'writable': True}},
        'config_schema': {'type': 'object', 'additionalProperties': True},
        'state_action': {'args': ['state']}
    }
    resource._docker_invoker = MockDockerInvoker(return_code=0, stderr='', stdout=json.dumps(init_result))
    with pytest.raises(UserError,
                       match=f"plug \'readonly_plug\' required by \'r1\' is readonly, but requested with write access"):
        resource.initialize()

    # test init action result requests a valid plug
    init_result: dict = {
        'plugs': {
            'readonly_plug': {'container_path': '/some/read/where', 'writable': False},
            'writable_plug': {'container_path': '/some/write/where', 'writable': True}
        },
        'config_schema': {'type': 'object', 'additionalProperties': True},
        'state_action': {'args': ['state']}
    }
    resource._docker_invoker = MockDockerInvoker(return_code=0, stderr='', stdout=json.dumps(init_result))
    resource.initialize()
    assert resource._plugs == {
        '/some/read/where': manifest.plug('readonly_plug'),
        '/some/write/where': manifest.plug('writable_plug')
    }
    assert resource._state_action.name == 'state'
    assert resource._state_action.description == 'Discover state of resource \'r1\''
    assert resource._state_action.image == resource.type
    assert resource._state_action.entrypoint is None
    assert resource._state_action.args == init_result['state_action']['args']
    assert resource._status == ResourceStatus.INITIALIZED
    assert resource._plug_volumes == [
        f"{str((scenario_dir / 'p2').absolute())}:{init_result['plugs']['readonly_plug']['container_path']}:ro",
        f"{str((scenario_dir / 'p1').absolute())}:{init_result['plugs']['writable_plug']['container_path']}:rw"
    ]
