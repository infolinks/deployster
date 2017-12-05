import os
import re

import jinja2
import yaml
from jinja2 import UndefinedError

from util import unindent, log, UserError, merge_into, bold, underline, indent


class Context:

    def __init__(self, version: str) -> None:
        self._version = version
        self._data: dict = {'version': self._version}

        # read auto vars files
        for file in os.listdir(os.path.expanduser('~/.deployster')):
            if re.match(r'^vars\.(.*\.)?auto\.yaml$', file):
                self.add_file(os.path.expanduser('~/.deployster/' + file))
        for file in os.listdir('.'):
            if re.match(r'^vars\.(.*\.)?auto\.yaml$', file):
                self.add_file('./' + file)

    @property
    def version(self) -> str:
        return self._version

    def add_file(self, path: str) -> None:
        with open(path, 'r') as stream:
            environment = jinja2.Environment(undefined=jinja2.StrictUndefined)
            try:
                source = yaml.load(environment.from_string(stream.read()).render(self.data))
            except UndefinedError as e:
                raise UserError(f"error in '{path}': {e.message}") from e
            merge_into(self._data, source)

    def add_variable(self, key: str, value: str) -> None:
        self._data[key] = value

    @property
    def data(self) -> dict:
        return self._data

    def display(self) -> None:
        log(bold(":paperclip: " + underline("Context:")))
        log('')
        indent()
        largest_name_length: int = len(max(list(self.data.keys()), key=lambda key: len(key)))
        for name, value in self.data.items():
            log(f":point_right: {name.ljust(largest_name_length,'.')}..: {bold(value)}")
        unindent()
        log('')
