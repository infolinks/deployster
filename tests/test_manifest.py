from pathlib import Path
from typing import Sequence, Tuple, MutableSequence, Mapping

import pytest
import yaml

from context import Context
from manifest import Action, Manifest, Resource
from manifest import Plug


@pytest.mark.parametrize("work_dir", [None, "/unknown/file", "./tests/.cache/action1"])
@pytest.mark.parametrize("name", [None, "", "action"])
@pytest.mark.parametrize("description", [None, "", "desssscriippttion"])
@pytest.mark.parametrize("image", [None, "", "immmaage"])
@pytest.mark.parametrize("entrypoint", [None, "", "ennntrrrypopiint"])
@pytest.mark.parametrize("args", [None, [], ["1"], ["1", "2"], ["1", "", ""]])
def test_action(work_dir: str, name: str, description: str, image: str, entrypoint: str, args: Sequence[str]):
    action: Action = Action(work_dir=Path(work_dir) if work_dir is not None else None,
                            name=name,
                            description=description,
                            image=image,
                            entrypoint=entrypoint, args=args)
    assert action.work_dir == (Path(work_dir) if work_dir is not None else None)
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
    assert plug.path == Path(path)
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
            if 'plugs' in expected:
                expected_plugs: dict = expected['plugs']
                for plug_name, expected_plug in expected_plugs.items():
                    plug: Plug = manifest.plug(plug_name)
                    if 'name' in expected_plug: assert plug.name == expected_plug['name']
                    if 'path' in expected_plug: assert plug.path == Path(expected_plug['path'])
                    if 'readonly' in expected_plug: assert plug.readonly == expected_plug['readonly']
                    if 'resource_name_patterns' in expected_plug:
                        assert plug.resource_name_patterns == expected_plug['resource_name_patterns']
                    if 'resource_type_patterns' in expected_plug:
                        assert plug.resource_type_patterns == expected_plug['resource_type_patterns']
            if 'resources' in expected:
                expected_resources: dict = expected['resources']
                for resource_name, expected_resource in expected_resources.items():
                    resource: Resource = manifest.resource(resource_name)
                    if 'readonly' in expected_resource: assert resource.readonly == expected_resource['readonly']
                    if 'name' in expected_resource: assert resource.name == expected_resource['name']
                    if 'type' in expected_resource: assert resource.type == expected_resource['type']
                    if 'config' in expected_resource: assert resource.config == expected_resource['config']
                    assert resource.status is None
                    if 'dependencies' in expected_resource:
                        assert resource.dependencies == expected_resource['dependencies']
