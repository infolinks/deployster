from pathlib import Path
from typing import Sequence

import pytest

from manifest import Plug


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
def test_new_action(name: str,
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
