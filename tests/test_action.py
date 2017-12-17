from pathlib import Path
from typing import Sequence

import pytest

from manifest import Action


@pytest.mark.parametrize("work_dir", [None, "/unknown/file", "./tests/.cache/action1"])
@pytest.mark.parametrize("name", [None, "", "action"])
@pytest.mark.parametrize("description", [None, "", "desssscriippttion"])
@pytest.mark.parametrize("image", [None, "", "immmaage"])
@pytest.mark.parametrize("entrypoint", [None, "",  "ennntrrrypopiint"])
@pytest.mark.parametrize("args", [None, [], ["1"], ["1", "2"], ["1", "", ""]])
def test_new_action(work_dir: str, name: str, description: str, image: str, entrypoint: str, args: Sequence[str]):
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
