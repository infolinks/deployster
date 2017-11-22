#!/usr/bin/env python3

import argparse
import json
import os
import pkgutil
import shutil
import subprocess
import traceback
from enum import Enum, unique, auto
from json import JSONDecodeError
from pathlib import Path
from typing import Sequence, Mapping, MutableMapping, Callable, MutableSequence, Any

import jinja2
import jsonschema
import yaml
from colors import bold, underline, red, italic, faint, yellow, green
from jinja2 import UndefinedError
from jsonschema import ValidationError

import util
from util import ask, log, warn, err, indent, unindent


class UserError(Exception):
    def __init__(self, message) -> None:
        super().__init__(message)
        self.message = message


class Context:
    def __init__(self) -> None:
        self._data: dict = {}

    def add_file(self, path: str) -> None:
        with open(path, 'r') as stream:
            if path.endswith('.json'):
                source = json.loads(stream)
            else:
                source = yaml.load(stream)
            util.merge_into(self._data, source)

    def add_variable(self, key: str, value: str) -> None:
        self._data[key] = value

    @property
    def data(self) -> dict:
        return self._data


class Resource:
    def __init__(self, name: str,
                 type: str,
                 readonly: bool,
                 config: dict = None,
                 dependencies: Mapping[str, str] = None) -> None:
        super().__init__()
        self._name: str = name
        self._type: str = type
        self._readonly: bool = readonly
        self._config: dict = config if config else {}
        self._dependencies: Mapping[str, str] = dependencies if dependencies else {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def type(self) -> str:
        return self._type

    @property
    def readonly(self) -> bool:
        return self._readonly

    @property
    def config(self) -> dict:
        return self._config

    @property
    def dependencies(self) -> Mapping[str, str]:
        return self._dependencies


class Plug:
    def __init__(self,
                 name: str,
                 path: str,
                 readonly: bool,
                 allowed_resource_names: Sequence[str],
                 allowed_resource_types: Sequence[str]):
        self._name: str = name
        self._path: Path = Path(os.path.expanduser(path=path))
        self._readonly: bool = readonly
        self._resource_names: Sequence[str] = allowed_resource_names
        self._resource_types: Sequence[str] = allowed_resource_types

    @property
    def name(self) -> str:
        return self._name

    @property
    def path(self) -> Path:
        return self._path

    @property
    def readonly(self) -> bool:
        return self._readonly

    @property
    def resource_names(self) -> Sequence[str]:
        return self._resource_names

    @property
    def resource_types(self) -> Sequence[str]:
        return self._resource_types

    def allowed_for(self, resource: Resource) -> bool:
        if resource.name in self.resource_names:
            return True

        resource_type = resource.type.split(':', 1)[0] if resource.type.find(':') >= 0 else resource.type
        valid_resource_types = [type.split(':', 1)[0] if type.find(':') >= 0 else type for type in self.resource_types]
        if resource_type in valid_resource_types:
            return True
        else:
            return len(self.resource_names) == 0 and len(self.resource_types) == 0


class Action:

    @staticmethod
    def from_json(data: dict,
                  default_name: str = None, default_description: str = None,
                  default_image: str = None, default_entrypoint: str = None, default_args: Sequence[str] = None):
        name: str = data['name'] if 'name' in data else default_name
        description: str = data['description'] if 'description' in data else default_description
        image: str = data['image'] if 'image' in data else default_image
        entrypoint: str = data['entrypoint'] if 'entrypoint' in data else default_entrypoint
        args: str = data['args'] if 'args' in data else default_args
        return Action(name=name, description=description, image=image, entrypoint=entrypoint, args=args)

    def __init__(self,
                 name: str,
                 description: str,
                 image: str,
                 entrypoint: str = None,
                 args: Sequence[str] = None) -> None:
        super().__init__()
        self._name: str = name
        self._description: str = description
        self._image: str = image
        self._entrypoint: str = entrypoint
        self._args: Sequence[str] = args if args else []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def image(self) -> str:
        return self._image

    @property
    def entrypoint(self) -> str:
        return self._entrypoint

    @property
    def args(self) -> Sequence[str]:
        return self._args

    def execute(self, work_dir: Path, volumes: Sequence[str] = None, stdin: dict = None):
        os.makedirs(str(work_dir), exist_ok=True)

        command = ["docker", "run", "-i"]

        # setup volumes
        if volumes:
            for volume in volumes:
                command.extend(["--volume", volume])

        # setup entrypoint
        if self.entrypoint:
            command.extend(["--entrypoint", self.entrypoint])

        # setup args
        command.append(self.image)
        if self.args:
            command.extend(self.args)

        # save stdin state file
        with open(work_dir / 'stdin.json', 'w') as f:
            f.write(json.dumps(stdin if stdin else {}, indent=2))

        # execute
        process = subprocess.run(command,
                                 input=json.dumps(stdin, indent=2) if stdin else '{}',
                                 encoding='utf-8',
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # save stdout & stderr state files
        with open(work_dir / 'stdout.json', 'w') as f:
            try:
                f.write(json.dumps(json.loads(process.stdout if process.stdout else '{}'), indent=2))
            except:
                f.write(process.stdout if process.stdout else '{}')
        with open(work_dir / 'stderr.json', 'w') as f:
            try:
                f.write(json.dumps(json.loads(process.stderr if process.stderr else '{}'), indent=2))
            except:
                f.write(process.stderr if process.stderr else '{}')

        # validate exit-code, fail if non-zero
        if process.returncode != 0:
            raise UserError(f"action '{self.name}' failed with exit code #{process.returncode}:\n{process.stderr}")

        # if JSON returned, read, parse & return that
        elif process.stdout:
            try:
                return json.loads(process.stdout)
            except JSONDecodeError as e:
                raise UserError(f"action '{self.name}' provided invalid JSON:\n{process.stdout}") from e

        # otherwise, return an empty dictionary
        else:
            return {}


class Manifest:
    schema = json.loads(pkgutil.get_data('schema', 'manifest.schema'))

    def __init__(self, context: Context, manifest_file: Path) -> None:
        super().__init__()
        self._manifest_file: Path = manifest_file

        # read manifest
        manifest: dict = {}
        with open(manifest_file, 'r') as f:
            environment = jinja2.Environment(undefined=jinja2.StrictUndefined)
            try:
                manifest = yaml.load(environment.from_string(f.read()).render(context.data))
            except UndefinedError as e:
                raise UserError(f"error in '{manifest_file}': {e.message}") from e

        # validate manifest against our manifest schema
        try:
            jsonschema.validate(manifest, Manifest.schema)
        except ValidationError as e:
            raise UserError(f"Manifest '{manifest_file}' failed validation: {e.message}") from e

        # parse plugs
        plugs: MutableMapping[str, Plug] = {}
        for plug_name, plug in (manifest['plugs'] if 'plugs' in manifest else {}).items():
            plugs[plug_name] = Plug(name=plug_name,
                                    path=plug['path'],
                                    readonly=plug['read_only'] if 'read_only' in plug else False,
                                    allowed_resource_names=plug['resource_names'] if 'resource_names' in plug else [],
                                    allowed_resource_types=plug['resource_types'] if 'resource_types' in plug else [])
        self._plugs: Mapping[str, Plug] = plugs

        # parse resources
        resources: MutableMapping[str, Resource] = {}
        for resource_name, resource in (manifest['resources'] if 'resources' in manifest else {}).items():
            resources[resource_name] = \
                Resource(name=resource_name,
                         type=resource['type'],
                         readonly=resource['readonly'] if 'readonly' in resource else False,
                         config=resource['config'] if 'config' in resource else {},
                         dependencies=resource['dependencies'] if 'dependencies' in resource else {})
        self._resources = resources

    @property
    def manifest_file(self) -> Path:
        return self._manifest_file

    def plug(self, name) -> Plug:
        return self._plugs[name] if name in self._plugs else None

    @property
    def plugs(self) -> Mapping[str, Plug]:
        return self._plugs

    def resource(self, name) -> Resource:
        return self._resources[name] if name in self._resources else None

    @property
    def resources(self) -> Mapping[str, Resource]:
        return self._resources


@unique
class ResourceStatus(Enum):
    MISSING = auto()
    STALE = auto()
    VALID = auto()


class ResourceState:
    init_action_stdout_schema = json.loads(pkgutil.get_data('schema', 'action-init-result.schema'))
    state_action_stdout_schema = json.loads(pkgutil.get_data('schema', 'action-state-result.schema'))

    def __init__(self, manifest: Manifest, resource: Resource, work_dir: Path,
                 resource_state_provider: Callable[[str], Any]) -> None:
        super().__init__()
        self._manifest: Manifest = manifest
        self._resource: Resource = resource
        self._work_dir: Path = work_dir
        self._config_schema: dict = None
        self._plugs: Mapping[str, Plug] = None
        self._dependencies: Mapping[str, Resource] = None
        self._state_action: Action = None
        self._status: ResourceStatus = None
        self._actions: Sequence[Action] = None
        self._properties: dict = None
        self._resource_state_provider = resource_state_provider
        self._type_label: str = None

        os.makedirs(str(self._work_dir), exist_ok=True)

    @property
    def manifest(self) -> Manifest:
        return self._manifest

    @property
    def resource(self) -> Resource:
        return self._resource

    @property
    def status(self) -> ResourceStatus:
        return self._status

    @property
    def icon(self) -> str:
        if self.status == ResourceStatus.VALID:
            return ":heavy_check_mark:"
        elif self.status == ResourceStatus.MISSING:
            return ":heavy_plus_sign:"
        elif self.status == ResourceStatus.STALE:
            return ":o:"
        else:
            raise Exception(f"unknown resource status: {self.status}")

    @property
    def actions(self) -> Sequence[Action]:
        return self._actions

    @property
    def properties(self) -> dict:
        return self._properties

    def get_as_dependency(self, include_properties: bool = True) -> dict:
        resolver = self._resource_state_provider
        data = {
            'name': self.resource.name,
            'type': self.resource.type,
            'config': self.resource.config,
            'dependencies': {
                k: resolver(v.name).get_as_dependency(include_properties) for k, v in self._dependencies.items()
            }
        }
        if include_properties:
            data['properties'] = self.properties
        return data

    def pull(self) -> None:
        process = subprocess.run(["docker", "pull", self.resource.type],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode != 0:
            raise UserError(f"pulling Docker image '{self.resource.type}' failed w/ exit code #{process.returncode}:\n"
                            f"{process.stderr}")

    def initialize(self) -> None:
        init_action = Action(name='init', description=f"Initialize '{self.resource.name}'",
                             image=self.resource.type, entrypoint=None, args=None)

        result = init_action.execute(work_dir=self._work_dir / init_action.name,
                                     stdin={
                                         'name': self.resource.name,
                                         'type': self.resource.type,
                                         'config': self.resource.config
                                     })
        self._type_label: str = result['label']

        # validate manifest against our manifest schema
        try:
            jsonschema.validate(result, ResourceState.init_action_stdout_schema)
        except ValidationError as e:
            raise UserError(f"Protocol error during initialization of '{self.resource.name}': {e.message}") from e

        # collect resource configuration schema, and if one was provided, validate resource configuration using it
        self._config_schema: dict = result['config_schema'] if 'config_schema' in result else None
        if self._config_schema:
            try:
                jsonschema.validate(self.resource.config, self._config_schema)
            except ValidationError as e:
                raise UserError(f"Invalid resource configuration for '{self.resource.name}': {e.message}") from e

        # collect required plugs, failing if any plug is missing
        plugs: MutableMapping[str, Plug] = {}
        for plug_name, container_path in (result['required_plugs'] if 'required_plugs' in result else {}).items():
            if plug_name not in self.manifest.plugs:
                raise UserError(f"resource '{self.resource.name}' requires missing plug '{plug_name}'")

            plug = self.manifest.plug(plug_name)
            if not plug.allowed_for(self.resource):
                raise UserError(f"plug '{plug_name}' is not allowed for resource '{self.resource.name}'")
            else:
                plugs[container_path] = plug
        self._plugs: Mapping[str, Plug] = plugs

        # collect required resources, failing if any resource is missing
        dependencies: MutableMapping[str, Resource] = {}
        for alias, type in (result['required_resources'] if 'required_resources' in result else {}).items():
            if alias not in self.resource.dependencies:
                raise UserError(f"dependency '{alias}' is missing for resource '{self.resource.name}' ({type})")
            type = type.split(':', 1)[0] if type.find(':') >= 0 else type

            source_resource_name = self.resource.dependencies[alias]
            if source_resource_name not in self.manifest.resources:
                raise UserError(f"resource '{source_resource_name}' required by '{self.resource.name}' does not exist.")

            source_resource = self.manifest.resource(source_resource_name)

            source_resource_type = source_resource.type.split(':', 1)[0] \
                if source_resource.type.find(':') >= 0 else source_resource.type
            if source_resource_type != type:
                raise UserError(
                    f"incorrect type for dependency '{source_resource_name}' of '{self.resource.name}', must be of "
                    f"type '{type}', but that resource is of type '{source_resource.type}'.")

            dependencies[alias] = source_resource
        self._dependencies: Mapping[str, Resource] = dependencies

        self._state_action: Action = \
            Action.from_json(data=result['state_action'],
                             default_name='state', default_description=f"Resolve state of '{self.resource.name}'",
                             default_image=self.resource.type, default_entrypoint=None, default_args=None)

    def resolve(self, force: bool = False, stealth: bool = False) -> None:
        if self._status is not None and not force:
            return

        # skip this resource if it's blocked by other resources that haven't been refreshed yet
        dependencies: MutableMapping[str, dict] = {}
        for dependency_alias, dependency_resource in self._dependencies.items():
            dependency_state: ResourceState = self._resource_state_provider(dependency_resource.name)
            if dependency_state.status is None:
                # one of our dependencies has not been resolved yet; abort.
                return
            elif dependency_state.status == ResourceStatus.MISSING:
                if not stealth:
                    log(f":point_right: {self.resource.name}")
                self._status: ResourceStatus = ResourceStatus.MISSING
                self._actions: Sequence[Action] = []
                return
            else:
                dependencies[dependency_alias] = dependency_state.get_as_dependency(include_properties=False)

        # execute state action
        if not stealth:
            log(f":point_right: {self.resource.name}")
            indent()

        # execute the resource state action
        result = self._state_action.execute(
            work_dir=self._work_dir / self._state_action.name,
            volumes=[f"{plug.path}:{cpath}:{'ro' if plug.readonly else 'rw'}" for cpath, plug in self._plugs.items()],
            stdin={
                'name': self.resource.name,
                'type': self.resource.type,
                'config': self.resource.config,
                'dependencies': dependencies
            })

        # validate manifest against our manifest schema
        try:
            jsonschema.validate(result, ResourceState.state_action_stdout_schema)
        except ValidationError as e:
            raise UserError(f"Protocol error while resolving '{self.resource.name}': {e.message}") from e

        # extract status & actions from state action's JSON in stdout
        status: ResourceStatus = ResourceStatus[result['status']]
        if status == ResourceStatus.VALID:
            if 'actions' in result and len(result['actions']):
                raise UserError(f"resource '{self.resource.name}' was stated to be VALID, yet has actions")
            elif 'properties' not in result:
                raise UserError(f"resource '{self.resource.name}' is VALID, but did not provide actual state")
            else:
                self._status: ResourceStatus = status
                self._actions: Sequence[Action] = []
                self._properties: dict = result['properties']
        elif 'properties' in result:
            raise UserError(f"resource '{self.resource.name}' was stated to be {status}, yet provided properties")
        elif 'actions' not in result or not len(result['actions']):
            raise UserError(f"resource '{self.resource.name}' is {status}, yet has no actions")
        elif self.resource.readonly:
            raise UserError(f"resource '{self.resource.name}' is declared as a read-only resource, but its status is "
                            f"{status}. Read-only resources are blocked from being updated, therefor this "
                            f"deployment plan is aborted.")
        else:
            self._status: ResourceStatus = status

            actions: list = []
            for action_dict in result['actions']:
                name = action_dict['name']
                description = action_dict['description'] if 'description' in action_dict else action_dict['name']
                image = action_dict['image'] if 'image' in action_dict else self.resource.type
                entrypoint = action_dict['entrypoint'] if 'entrypoint' in action_dict else None
                args = action_dict['args'] if 'args' in action_dict else None
                action = Action(name=name, description=description, image=image, entrypoint=entrypoint, args=args)
                actions.append(action)
            self._actions: Sequence[Action] = actions
            self._properties: dict = None
        if not stealth:
            unindent()

    def execute(self) -> None:
        resolver: Callable[[str], ResourceState] = self._resource_state_provider

        # if this resource was marked as MISSING because (during planning) one or more of its dependencies was MISSING,
        # it's now time to refresh our status, since by now, our dependencies should have been created.
        if self.status == ResourceStatus.MISSING and len(self.actions) == 0:
            self.resolve(force=True, stealth=True)
            if self.status == ResourceStatus.VALID:
                log(yellow(bold(f"WARNING: this resource was considered MISSING because one or more of its "
                                f"         dependencies was missing; now that its dependencies have been resolved, "
                                f"         it seems this resource is now VALID - this is probably a bug in the "
                                f"         '{self.resource.type}' resource image.")))
                return

        for action in self._actions:
            log(f":wrench: {action.description} ({action.name})")
            log('')
            indent()
            # TODO: stream stderr/stdout from the action to deployster console (we don't expect JSON from this action)
            action.execute(
                work_dir=self._work_dir / action.name,
                volumes=[f"{p.path}:{cpath}:{'ro' if p.readonly else 'rw'}" for cpath, p in self._plugs.items()],
                stdin={
                    'name': self.resource.name,
                    'type': self.resource.type,
                    'config': self.resource.config,
                    'dependencies': {k: resolver(v.name).get_as_dependency() for k, v in self._dependencies.items()}
                })
            unindent()

        # refresh to receive updated properties
        self.resolve(force=True, stealth=True)
        if self.status != ResourceStatus.VALID:
            raise UserError(f"resource '{self.resource.name}' was expected to be VALID after its actions have been "
                            f"executed, but instead, the status is '{self.status}'.")


class Plan:

    def __init__(self, work_dir: Path, manifest: Manifest) -> None:
        super().__init__()
        self._work_dir: Path = work_dir
        self._manifest: Manifest = manifest
        self._resource_states: Mapping[str, ResourceState] = \
            {
                r.name: ResourceState(manifest=manifest, resource=r, work_dir=work_dir / r.name,
                                      resource_state_provider=lambda name: self._resource_states[name])
                for r in manifest.resources.values()
            }
        self._deployment_sequence: Sequence[ResourceState] = None

    @property
    def work_dir(self) -> Path:
        return self._work_dir

    @property
    def manifest(self) -> Manifest:
        return self._manifest

    @property
    def deployment_sequence(self) -> Sequence[ResourceState]:
        return self._deployment_sequence

    def validate_docker_available(self) -> None:
        log(f":wrench: Verifying Docker is up...")
        indent()
        process = subprocess.run(["docker", "run", "hello-world"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode != 0:
            raise UserError(f"Docker is not available. Here's output from a test run:\n"
                            f"=======================================================\n"
                            f"{process.stderr.decode('utf-8')}")
        unindent()

    def clean_work_dir(self) -> None:
        log(f":wrench: Setting up work directory at '{self.work_dir}'...")
        indent()
        try:
            shutil.rmtree(str(self.work_dir))
        except FileNotFoundError:
            pass
        os.makedirs(str(self.work_dir))
        unindent()

    def bootstrap(self, pull=True) -> None:
        log(bold(":hourglass: " + underline("Bootstrapping:")))
        log('')

        indent()
        self.validate_docker_available()
        self.clean_work_dir()
        if pull:
            for state in self._resource_states.values():
                log(f":point_right: Pulling Docker image for resource '{bold(state.resource.name)}'...")
                indent()
                state.pull()
                unindent()
        else:
            warn(f":point_right: Skipping explicit resource image pulling")

        for state in self._resource_states.values():
            log(f":point_right: Initializing resource '{bold(state.resource.name)}'")
            indent()
            state.initialize()
            unindent()

        unindent()
        log('')

    def resolve(self) -> None:
        log(bold(":mag_right: " + underline("Discovery:")))
        log('')

        indent()
        deployment_sequence: MutableSequence[ResourceState] = []
        while True:

            # remember how many unresolved resources we currently have
            pre_unresolved_count = len([state for state in self._resource_states.values() if state.status is None])

            # attempt to resolve as many as we can, skipping resources that await other resources to be resolved
            for state in self._resource_states.values():
                state.resolve()
                if state.status != ResourceStatus.VALID:
                    deployment_sequence.append(state)

            # check how many unresolved resources we now have
            post_unresolved_count = len([state for state in self._resource_states.values() if state.status is None])

            # if all resources have been resolved, we're done
            # otherwise, if not even one resource has been resolved in the last loop, we've detected a circular
            # dependency (abort)
            if post_unresolved_count == 0:
                break
            elif pre_unresolved_count == post_unresolved_count:
                raise UserError(f"circular dependency encountered!")
        self._deployment_sequence = deployment_sequence
        unindent()
        log('')

    @property
    def empty(self) -> bool:
        return self._deployment_sequence is not None and len(self._deployment_sequence) == 0

    def display(self):
        log(bold(":clipboard: " + underline("Deployment plan:")))
        log('')

        indent()
        if self.empty:
            log(f"No action necessary.")
            log('')
        else:
            for state in [state for state in self._deployment_sequence if state.status != ResourceStatus.VALID]:
                log(f"{state.icon} {state.resource.name} ({faint(italic(state.resource.type))})")
                log('')
                indent()
                if state.status == ResourceStatus.MISSING and len(state.actions) == 0:
                    log(f":wrench: Create resource '{state.resource.name}' "
                        f"({faint(italic('one or more dependencies are missing'))})")
                    log('')
                else:
                    for action in state.actions:
                        log(f":wrench: {action.description} ({faint(italic(action.name))})")
                        log('')
                unindent()
        unindent()

    def execute(self):
        log(bold(":dizzy: " + underline("Execution:")))
        log('')

        indent()
        for state in [state for state in self._deployment_sequence if state.status != ResourceStatus.VALID]:
            log(f"{state.icon} {state.resource.name} ({state.resource.type})")
            log('')
            indent()
            state.execute()
            unindent()
        unindent()


def main():
    if os.path.exists("/deployster/VERSION"):
        with open("/deployster/VERSION", 'r') as f:
            version = f.read().strip()
    else:
        version = "0.0.0"
    log(green(underline(bold(f"Deployster v{version}"))))
    log('')

    class VariableAction(argparse.Action):

        def __init__(self, option_strings, dest, nargs=None, const=None, default=None, type=None, choices=None,
                     required=False, help=None, metavar=None):
            if const is not None:
                raise ValueError("'const' not allowed with VariableAction")
            if type is not None and type != str:
                raise ValueError("'type' must be 'str' (or None)")
            super().__init__(option_strings, dest, nargs, const, default, type, choices, required, help, metavar)

        def __call__(self, parser, namespace, values, option_string=None):
            if not hasattr(namespace, self.dest) or not getattr(namespace, self.dest):
                setattr(namespace, self.dest, Context())
            context: Context = getattr(namespace, self.dest)

            tokens = values.split('=', 1)
            if len(tokens) != 2:
                raise argparse.ArgumentTypeError(f"bad variable: '{values}'")
            else:
                var_name = tokens[0]
                var_value = tokens[1]
                if var_value[0] == '"' and var_value[-1] == '"':
                    var_value = var_value[1:-1]
                context.add_variable(var_name, var_value)

    class VariablesFileAction(argparse.Action):

        def __init__(self, option_strings, dest, nargs=None, const=None, default=None, type=None, choices=None,
                     required=False, help=None, metavar=None):
            if const is not None:
                raise ValueError("'const' not allowed with VariableAction")
            if type is not None and type != str:
                raise ValueError("'type' must be 'str' (or None)")
            super().__init__(option_strings, dest, nargs, const, default, type, choices, required, help, metavar)

        def __call__(self, parser, namespace, values, option_string=None):
            if os.path.exists(values):
                if not hasattr(namespace, self.dest) or not getattr(namespace, self.dest):
                    setattr(namespace, self.dest, Context())
                context: Context = getattr(namespace, self.dest)
                context.add_file(values)
            else:
                warn(yellow(
                    f"WARNING: context file '{values}' does not exist (manifest processing might result in errors)."))

    # parse arguments
    argparser = argparse.ArgumentParser(description=f"Deployment automation tool, v{version}.",
                                        epilog="Written by Infolinks Inc. (https://github.com/infolinks/deployster)")
    argparser.add_argument('--no-pull', dest='pull', action='store_false',
                           help='skip resource Docker images pulling (rely on Docker default)')
    argparser.add_argument('--var', action=VariableAction, metavar='NAME=VALUE', dest='context',
                           help='makes the given variable available to the deployment manifest')
    argparser.add_argument('--var-file', action=VariablesFileAction, metavar='FILE', dest='context',
                           help='makes the variables in the given file available to the deployment manifest')
    argparser.add_argument('manifest', help='the deployment manifest to execute.')
    argparser.add_argument('-p', '--plan', action='store_true', dest='plan', help="print deployment plan and exit")
    argparser.add_argument('-y', '--yes', action='store_true', dest='assume_yes',
                           help="don't ask for confirmation before executing the deployment plan.")
    argparser.add_argument('-v', '--verbose', action='store_true', dest='verbose', help="print debugging information.")
    args = argparser.parse_args()
    log('')

    try:
        context: Context = args.context
        if args.verbose:
            log(f"Context: {json.dumps(context.data, indent=2)}")

        # load manifest
        manifest: Manifest = Manifest(context=context, manifest_file=args.manifest)

        # build the deployment plan, display, and potentially execute it
        work_path = Path(f"/deployster/work/{os.path.basename(args.manifest)}")
        plan: Plan = Plan(work_dir=work_path.resolve(), manifest=manifest)
        plan.bootstrap(args.pull)
        plan.resolve()
        plan.display()
        if args.plan or plan.empty:
            exit(0)

        execute_plan: bool = args.assume_yes or ask(bold('Execute?'), chars='yn', default='n') == 'y'
        log('')

        if execute_plan:
            plan.execute()

    except UserError as e:
        if args.verbose:
            err(red(traceback.format_exc()))
        else:
            err(red(e.message))
        exit(1)
    except KeyboardInterrupt:
        unindent(fully=True)
        err('')
        err(red(f"Interrupted."))
        exit(1)
    except Exception:
        # always print stacktrace since this exception is an unexpected exception
        err(red(traceback.format_exc()))
        exit(1)


if __name__ == "__main__":
    main()
