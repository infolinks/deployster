import json
import os
import subprocess
from copy import deepcopy
from json import JSONDecodeError
from pathlib import Path

from colors import italic, red, faint

from deployster.Util import log, err, indent, unindent
from deployster.resource.DockerError import DockerError
from deployster.resource.ResourceActionError import ResourceActionError
from deployster.resource.ResourceInitError import ResourceInitError
from deployster.resource.ResourceState import ResourceState
from deployster.resource.ResourceStateError import ResourceStateError


class Resource:

    def __init__(self, deployment, name, data):
        self._deployment = deployment
        self._name = name
        self._type = data['type']
        self._properties = data['properties']
        self._plugs = {}
        self._state = {}
        self._state_entrypoint = None

        # create work dir
        os.makedirs(self.work_dir)

        # find dependencies of this resource
        self._dependencies = []
        for k, v in self._properties.items():
            if isinstance(v, str):
                if v.startswith('~'):
                    self._dependencies.append(v[1:])

        log(italic(f"Initializing '{self.name}'..."))
        indent()
        try:
            init = self.execute_command({'name': self.name, 'properties': self.properties})
            if 'state_entrypoint' not in init or not isinstance(init['state_entrypoint'], str):
                raise ResourceInitError(f"missing or invalid 'state_entrypoint'", self)
            else:
                self._state_entrypoint = init['state_entrypoint']

            if 'requires' in init:
                if not isinstance(init['requires'], dict):
                    raise ResourceInitError(f"invalid 'requires' provided: {init['requires']}", self)
                else:
                    for plug_name, target_path in init['requires'].items():
                        if plug_name in self._deployment.plugs:
                            self._plugs[plug_name] = {
                                'target_path': target_path,
                                'plug': self._deployment.plugs[plug_name]
                            }
                        else:
                            raise ResourceInitError(f"required plug '{plug_name}' is missing", self)

        except ResourceInitError as e:
            err(red(f"resource '{self.name}' failed to initialize, {e.message}"))
            exit(1)

        except DockerError as e:
            err(red(f"resource '{self.name}' failed to initialize, {e.message}"))
            err(red(e.process.stderr))
            exit(1)
        finally:
            unindent()

    def refresh_state(self):
        log(italic(f"Refreshing '{self.name}'..."))
        indent()
        try:
            result = self.execute_command({'name': self.name, 'properties': self.expand_properties()},
                                          entrypoint=self._state_entrypoint)

            # persist state
            state_file = open(self.work_dir / 'state.json', 'w')
            state_file.write(json.dumps(result, indent=2))
            state_file.close()

            self._state = ResourceState(self, result)
            unindent()

        except DockerError as e:
            err('')
            err(red(e.message))
            err(red(e.process.stderr))
            exit(1)

        except ResourceActionError as e:
            err('')
            err(red(e.message))
            exit(1)

        except ResourceStateError as e:
            err('')
            err(red(e.message))
            exit(1)

    @property
    def deployment(self):
        return self._deployment

    @property
    def name(self):
        return self._name

    @property
    def type(self):
        return self._type

    @property
    def properties(self):
        return self._properties

    @property
    def plugs(self):
        return self._plugs

    @property
    def state(self):
        return self._state

    @property
    def dependencies(self):
        return self._dependencies

    def depends_on(self, resource):
        for dependency in self.dependencies:
            if dependency is resource or dependency.depends_on(resource):
                return True
        return False

    @property
    def work_dir(self):
        return self.deployment.work_dir / self.name

    def expand_properties(self):
        data_copy = deepcopy(self._properties)
        self._expand_dict(data_copy)
        return data_copy

    def _expand_dict(self, data):
        for k, v in data.items():
            if isinstance(v, str) and v.startswith('~'):
                data[k] = self._deployment.resources[v[1:]].state.properties
            elif isinstance(v, dict):
                self._expand_dict(v)

    def execute_command(self, stdin=None, entrypoint='', args=None):
        command = ["docker", "run", "-i"]
        command.extend(["--volume", f"{Path.cwd()}:/var/lib/deployster/workspace"])
        command.extend(["--volume", f"{self.work_dir}:/var/lib/deployster/resource"])
        for plug_name, plug_info in self.plugs.items():
            target_path = plug_info['target_path']
            plug = plug_info['plug']
            command.extend(["--volume", f"{plug.path}:{target_path}"])
        if entrypoint:
            command.extend(["--entrypoint", entrypoint])
        command.append(self._type)
        if args:
            command.extend(args)

        if self.deployment.verbose:
            log(faint(f"Input for Docker command: {json.dumps(stdin,indent=2)}"))

        process = subprocess.run(command,
                                 input=json.dumps(stdin) if stdin else None,
                                 encoding='utf-8',
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if self.deployment.verbose:
            if process.stdout:
                try:
                    log(faint(f"Docker process stdout: {json.dumps(json.loads(process.stdout),indent=2)}"))
                except:
                    err(faint(f"Docker process stdout (raw): {process.stdout}"))
            if process.stderr:
                try:
                    log(faint(f"Docker process stderr: {json.dumps(json.loads(process.stderr),indent=2)}"))
                except:
                    err(faint(f"Docker process stderr (raw): {process.stderr}"))

        if process.returncode != 0:
            raise DockerError(f"exit code #{process.returncode}", process)
        elif process.stdout:
            try:
                return json.loads(process.stdout)
            except JSONDecodeError as e:
                raise DockerError(f"invalid JSON: {process.stdout}", process) from e
        else:
            return {}
