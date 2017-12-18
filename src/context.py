import os
import re
from enum import Enum, auto, unique
from pathlib import Path
from typing import Any

import yaml

import util
from util import UserError, merge_into, bold, underline, Logger, italic


# TODO: split this class to 'Config' and 'Context'
@unique
class ConfirmationMode(Enum):
    NO = auto()
    ONCE = auto()
    RESOURCE = auto()
    ACTION = auto()


class Context:

    def __init__(self, version_file_path: str = '/deployster/VERSION', env: dict = os.environ) -> None:
        self._data = {}

        # read version
        if os.path.exists(version_file_path):
            with open(version_file_path, 'r') as f:
                self.add_variable('_version', f.read().strip())
        else:
            self.add_variable('_version', "0.0.0")

        # whether increased verbosity was requested
        self.add_variable('_verbose',
                          True if "VERBOSE" in env and env["VERBOSE"].lower() in ['1', 'yes', 'true'] else False)

        # work paths
        self.add_variable('_conf', env["CONF_DIR"] if 'CONF_DIR' in env else os.path.expanduser('~/.deployster'))
        self.add_variable('_workspace', env["WORKSPACE_DIR"] if 'WORKSPACE_DIR' in env else os.path.abspath('.'))
        self.add_variable('_work', env["WORK_DIR"] if 'WORK_DIR' in env else os.path.abspath('./work'))
        self.add_variable('_confirm', ConfirmationMode.ACTION.name)

    def load_auto_files(self) -> None:
        if os.path.exists(self.conf_dir) and os.path.isdir(self.conf_dir):
            for file in os.listdir(str(self.conf_dir)):
                if re.match(r'^vars\.(.*\.)?auto\.yaml$', file):
                    self.add_file(str(self.conf_dir) + '/' + file)
        if os.path.exists(self.workspace_dir) and os.path.isdir(self.workspace_dir):
            for file in os.listdir(str(self.workspace_dir)):
                if re.match(r'^vars\.(.*\.)?auto\.yaml$', file):
                    self.add_file(str(self.workspace_dir) + '/' + file)

    @property
    def confirm(self) -> ConfirmationMode:
        return ConfirmationMode[self._data['_confirm']]

    @confirm.setter
    def confirm(self, value: ConfirmationMode):
        self.add_variable('_confirm', value.name)

    @property
    def conf_dir(self) -> Path:
        return Path(self._data['_conf'])

    @property
    def workspace_dir(self) -> Path:
        return Path(self._data['_workspace'])

    @property
    def work_dir(self) -> Path:
        return Path(self._data['_work'])

    @property
    def version(self) -> str:
        return self.data['_version']

    @property
    def verbose(self) -> bool:
        return self.data['_verbose']

    @verbose.setter
    def verbose(self, value: bool):
        self.add_variable('_verbose', value)

    def add_file(self, path: str) -> None:
        with open(path, 'r') as stream:
            try:
                source = yaml.load(stream.read())
            except yaml.YAMLError as e:
                raise UserError(f"illegal config: malformed variables file at '{path}': {e}") from e
            merge_into(self._data, util.post_process(value=source, context=self.data))

    def add_variable(self, key: str, value: Any) -> None:
        self._data[key] = value

    @property
    def data(self) -> dict:
        return self._data

    def display(self) -> None:
        with Logger(header=f":clipboard: {underline('Context:')}") as logger:
            largest_name_length: int = len(max(list(self.data.keys()), key=lambda key: len(key)))
            for name in sorted(self.data.keys()):
                msg: str = f":point_right: {name.ljust(largest_name_length,'.')}..: {bold(str(self.data[name]))}"
                if name.startswith("_"):
                    msg = italic(msg)
                logger.info(msg)
