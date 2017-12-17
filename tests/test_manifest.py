import os
from pathlib import Path
from typing import Sequence, Tuple, MutableSequence, Mapping

import pytest

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


def find_scenarios() -> Sequence[Tuple[str, Path, Sequence[Path]]]:
    scenarios: MutableSequence[Tuple[str, Path, Sequence[Path]]] = []
    root: Path = Path('./tests/manifest_scenarios')
    for scenario_dir in root.iterdir():
        if scenario_dir.is_dir():
            scenarios.append((
                scenario_dir.name,
                scenario_dir,
                [scenario_dir / file for file in os.listdir(str(scenario_dir))]
            ))
    return scenarios


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


@pytest.mark.parametrize("description,dir,manifest_files", find_scenarios())
def test_manifest(capsys, description: str, dir: Path, manifest_files: Sequence[Path]):
    context: Context = Context(version_file_path='./tests/test_version', env={
        "CONF_DIR": str(dir.absolute() / 'conf'),
        "WORKSPACE_DIR": str(dir.absolute()),
        "WORK_DIR": str(Path('./tests/.cache/manifest_scenarios') / description)
    })
    context.add_variable("k1", "v1")
    context.add_variable("k2", "v2")

    Manifest(context=context, manifest_files=manifest_files, resource_factory=MockResource)
