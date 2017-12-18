import os
import re
from pathlib import Path

import pytest
from _pytest.capture import CaptureResult

from context import Context, ConfirmationMode
from util import UserError


@pytest.mark.parametrize("version_file", ["/unknown/file", "./tests/test_version"])
@pytest.mark.parametrize("verbose", ["true", "1", "0", "false"])
@pytest.mark.parametrize("conf_dir", ["./tests/.cache/conf"])
@pytest.mark.parametrize("workspace_dir", ["./tests/.cache/workspace"])
@pytest.mark.parametrize("work_dir", ["./tests/.cache/workspace/work"])
def test_new_context(version_file: str, verbose: str, conf_dir: str, workspace_dir: str, work_dir: str):
    context: Context = Context(version_file_path=version_file, env={
        "VERBOSE": verbose,
        "CONF_DIR": conf_dir,
        "WORKSPACE_DIR": workspace_dir,
        "WORK_DIR": work_dir
    })
    assert context.version == ('1.2.3' if os.path.exists(version_file) else "0.0.0")
    assert context.verbose == (verbose == "true" or verbose == "1" or verbose == "yes")
    assert context.conf_dir == Path(conf_dir)
    assert context.workspace_dir == Path(workspace_dir)
    assert context.work_dir == Path(work_dir)
    assert context.confirm == ConfirmationMode.ACTION


def test_verbose_setter():
    context: Context = Context()
    assert not context.verbose

    context.verbose = True
    assert context.verbose


@pytest.mark.parametrize("conf_dir", ["./tests/.cache/conf", "/conf/dir"])
@pytest.mark.parametrize("workspace_dir", ["./tests/.cache/workspace", "/workspace/dir"])
def test_load_auto_vars_files(conf_dir: str, workspace_dir: str):
    context: Context = Context(env={
        "CONF_DIR": conf_dir,
        "WORKSPACE_DIR": workspace_dir
    })
    assert context.conf_dir == Path(conf_dir)
    assert context.workspace_dir == Path(workspace_dir)

    expected_foo1 = 'foo1_original'
    context.add_variable('foo1', expected_foo1)
    expected_foo2 = 'foo2_original'
    context.add_variable('foo2', expected_foo2)

    if conf_dir.startswith("./"):
        os.makedirs(conf_dir, exist_ok=True)
        with open(Path(conf_dir) / 'vars.auto.yaml', 'w') as f:
            expected_foo1 = 'bar1'
            f.write(f'foo1: {expected_foo1}')
        with open(Path(conf_dir) / 'vars.notauto.yaml', 'w') as f:
            f.write(f'foo2: will_not_be_added_{expected_foo2}')

    if workspace_dir.startswith("./"):
        os.makedirs(workspace_dir, exist_ok=True)
        with open(Path(workspace_dir) / 'vars.auto.yaml', 'w') as f:
            expected_foo2 = 'bar2'
            f.write(f'foo2: {expected_foo2}')
        with open(Path(workspace_dir) / 'vars.notauto.yaml', 'w') as f:
            f.write(f'foo2: will_not_be_added_{expected_foo2}')

    context.load_auto_files()
    assert context.data['foo1'] == expected_foo1
    assert context.data['foo2'] == expected_foo2


# noinspection PyTypeChecker
@pytest.mark.parametrize("mode", list(ConfirmationMode))
def test_confirm(mode: ConfirmationMode):
    context: Context = Context()
    assert context.confirm == ConfirmationMode.ACTION

    context.confirm = mode
    assert context.confirm == mode


@pytest.mark.parametrize("name,value", [("k1", "v1"), ("k1", ""), ("k1", None)])
def test_add_variable(name: str, value: str):
    context: Context = Context()
    context.add_variable(name, value)
    assert context.data[name] == value


def test_add_file_not_existing():
    path: str = '/unknown/dir/vars.yaml'
    with pytest.raises(FileNotFoundError):
        Context().add_file(path)


def test_add_file_invalid():
    path: str = './tests/.cache/workspace/vars.yaml'
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with pytest.raises(UserError):
        with open('./tests/.cache/workspace/vars.yaml', 'w') as f:
            f.write('foo: {{aaa}}}')
        Context().add_file(path)

    with pytest.raises(UserError):
        with open('./tests/.cache/workspace/vars.yaml', 'w') as f:
            f.write('foo: "{{aaa}}}"')
        Context().add_file(path)

    with pytest.raises(UserError):
        with open('./tests/.cache/workspace/vars.yaml', 'w') as f:
            f.write('foo: "{{aaa"')
        Context().add_file(path)


def test_var_referencing():
    path: str = './tests/.cache/workspace/vars.yaml'
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open('./tests/.cache/workspace/vars.yaml', 'w') as f:
        f.write('s: abc\n'
                'n: "{{ prev_n + 1 }}"')
    context: Context = Context()
    context.add_variable('prev_n', 1)
    context.add_file(path)
    assert context.data['prev_n'] == 1
    assert context.data['n'] == 2
    assert context.data['s'] == 'abc'


@pytest.mark.parametrize("name,value", [("k1", "v1"), ("k1", "")])
def test_display(capsys, name: str, value: str):
    context: Context = Context()
    context.add_variable(name, value)
    context.display()

    captured: CaptureResult = capsys.readouterr()
    assert [line for line in captured.out.split("\n") if re.match(r'.*' + name + r'.*' + value, line)]
