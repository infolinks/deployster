import json

import yaml

from deployster import Util


class Context:

    def __init__(self):
        self._data = {}

    def add_file(self, path):
        with open(path, 'r') as stream:
            if path.endswith('.json'):
                source = json.loads(stream)
            else:
                source = yaml.load(stream)
            Util.merge_into(self._data, source)

    def add_variable(self, key, value):
        self._data[key] = value

    @property
    def data(self):
        return self._data
