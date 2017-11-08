import json

from deployster.Util import log, indent, unindent, err, red
from deployster.resource.DockerError import DockerError
from deployster.resource.ResourceActionError import ResourceActionError


class ResourceAction:

    def __init__(self, resource, data):
        self._resource = resource
        if not isinstance(data, dict):
            raise ResourceActionError(f"invalid action encountered (not an object: {data})")
        elif 'name' not in data or not isinstance(data['name'], str):
            raise ResourceActionError(f"invalid action encountered (missing or invalid 'name')")
        elif 'description' not in data or not isinstance(data['description'], str):
            raise ResourceActionError(f"action '{data['name']}' is invalid (missing or invalid 'description')")
        elif 'entrypoint' not in data or not isinstance(data['entrypoint'], str):
            raise ResourceActionError(f"action '{data['name']}' is invalid (missing or invalid 'entrypoint')")
        else:
            self._name = data['name']
            self._description = data['description']
            self._entrypoint = data['entrypoint']
            self._args = data['args'] if 'args' in data else []

    @property
    def resource(self):
        return self._resource

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return self._description

    @property
    def entrypoint(self):
        return self._entrypoint

    @property
    def args(self):
        return self._args

    def execute(self):
        log(f"{self.name} @ {self.resource.name}")
        indent()
        try:
            result = self.resource.execute_command(
                {
                    'name': self.resource.name,
                    'properties': self.resource.expand_properties(),
                    'state': self.resource.state.properties
                },
                entrypoint=self._entrypoint,
                args=self._args)

            # persist state
            result_file = open(f"{self.resource.work_dir}/{self.name}.json", 'w')
            result_file.write(json.dumps(result, indent=2))
            result_file.close()

            # refresh resource
            self.resource.refresh_state()

        except DockerError as e:
            err('\n')
            err(red(e.message))
            err(red(e.process.stderr))
            exit(1)

        unindent()
