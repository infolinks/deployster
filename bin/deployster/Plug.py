import os
from pathlib import Path

from deployster.resource import Resource


class Plug:

    def __init__(self, name, data):
        self._name = name
        self._path = Path(os.path.expanduser(data['path']))
        self._resource_names = data['resource_names']
        self._resource_types = data['resource_types']

    @property
    def name(self):
        return self._name

    @property
    def path(self):
        return self._path

    @property
    def resource_names(self):
        return self._resource_names

    @property
    def resource_types(self):
        return self._resource_types

    def allowed_for(self, resource: Resource):
        if resource.name in self.resource_names:
            return True
        elif resource.type in self.resource_types:
            return True
        else:
            return len(self.resource_names) == 0 and len(self.resource_types) == 0
