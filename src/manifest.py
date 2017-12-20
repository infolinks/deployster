import json
import os
import pkgutil
import re
from copy import deepcopy
from enum import auto, Enum, unique
from pathlib import Path
from typing import Mapping, Sequence, Pattern, MutableMapping, Callable

import jsonschema
import yaml
from jsonschema import ValidationError

import util
from context import Context, ConfirmationMode
from docker import DockerInvoker
from util import UserError, bold, underline, Logger, faint, italic, post_process, ask


class Action:

    def __init__(self,
                 work_dir: Path,
                 name: str,
                 description: str,
                 image: str,
                 entrypoint: str = None,
                 args: Sequence[str] = None) -> None:
        super().__init__()
        self._work_dir = work_dir.absolute()
        self._name: str = name
        self._description: str = description
        self._image: str = image
        self._entrypoint: str = entrypoint
        self._args: Sequence[str] = args if args else []

    @property
    def work_dir(self) -> Path:
        return self._work_dir

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


@unique
class ResourceStatus(Enum):
    INITIALIZED = auto()
    RESOLVING = auto()
    STALE = auto()
    VALID = auto()


class Resource:
    init_action_stdout_schema = json.loads(pkgutil.get_data('schema', 'action-init-result.schema'))
    state_action_stdout_schema = json.loads(pkgutil.get_data('schema', 'action-state-result.schema'))

    def __init__(self,
                 manifest: 'Manifest',
                 name: str,
                 type: str,
                 readonly: bool,
                 config: dict = None,
                 dependencies: Mapping[str, 'Resource'] = None,
                 docker_invoker: DockerInvoker = None) -> None:
        super().__init__()
        self._manifest: 'Manifest' = manifest
        self._status: ResourceStatus = None
        self._name: str = name

        if re.match(r'^infolinks/deployster-[^:]+$', type):
            type = type + ':' + manifest.context.version
        self._type: str = type
        self._readonly: bool = readonly
        self._config_schema: dict = None
        self._config: dict = config if config else {}
        self._resolved_config: dict = None
        self._dependencies: Mapping[str, 'Resource'] = dependencies if dependencies else {}
        self._docker_volumes: Sequence[str] = [
            f"{manifest.context.conf_dir}:{manifest.context.conf_dir}:ro",
            f"{manifest.context.workspace_dir}:{manifest.context.workspace_dir}:ro",
            f"{manifest.context.work_dir}:{manifest.context.work_dir}:rw",
        ]
        self._plug_volumes: Sequence[str] = None
        self._docker_invoker: DockerInvoker = \
            docker_invoker if docker_invoker is not None else DockerInvoker(volumes=self._docker_volumes)
        self._plugs: MutableMapping[str, Plug] = {}
        self._state_action: Action = None
        self._state: dict = None
        self._apply_actions: Sequence[Action] = None

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
    def dependencies(self) -> Mapping[str, 'Resource']:
        return self._dependencies

    @property
    def status(self) -> ResourceStatus:
        return self._status

    @property
    def state(self) -> dict:
        return self._state

    def initialize(self) -> None:
        with Logger(f":point_right: Initializing '{bold(self.name)}' ({italic(faint(self.type))})",
                    spacious=False) as logger:

            # execute resource Docker image with the default entrypoint
            # TODO: consider caching init results since they are not expected to change per resource-type
            result = self._docker_invoker.run_json(
                logger=logger,
                local_work_dir=self._manifest.context.work_dir / self.name / "init",
                container_work_dir=str(self._manifest.context.workspace_dir),
                image=self.type,
                input={
                    'name': self.name,
                    'type': self.type,
                    'version': self._manifest.context.version,
                    'verbose': self._manifest.context.verbose,
                    'workspace': str(self._manifest.context.workspace_dir)
                })

            # validate manifest against our manifest schema
            try:
                jsonschema.validate(result, Resource.init_action_stdout_schema)
            except ValidationError as e:
                raise UserError(
                    f"protocol error: '{self.name}' initialization result failed validation: {e.message}") from e

            # store config schema
            self._config_schema = result['config_schema'] if 'config_schema' in result else {
                'type': 'object',
                'additionalProperties': True
            }

            # parse, validate & collect requested plugs
            plugs: MutableMapping[str, Plug] = {}
            for plug_name, plug_spec in (result['plugs'] if 'plugs' in result else {}).items():
                optional = plug_spec['optional'] if 'optional' in plug_spec else False
                require_writable = plug_spec['writable'] if 'writable' in plug_spec else True

                if plug_name not in self._manifest.plugs:
                    if optional:
                        logger.warn(f"Optional plug '{plug_name}' does not exist (skipped)")
                        continue
                    else:
                        raise UserError(
                            f"illegal config: plug '{plug_name}' required by '{self.name}' does not exist")

                plug = self._manifest.plug(plug_name)
                if not plug.allowed_for(self.name, self.type):
                    if optional:
                        logger.warn(f"Optional plug '{plug_name}' is not allowed for this resource (skipped)")
                        continue
                    else:
                        raise UserError(
                            f"illegal config: plug '{plug_name}' required by '{self.name}' is not allowed for it")
                elif require_writable and plug.readonly:
                    if optional:
                        logger.warn(
                            f"Optional plug '{plug_name}' is readonly, but requested with write access (denied)")
                        continue
                    else:
                        raise UserError(
                            f"illegal config: plug '{plug_name}' required by '{self.name}' is readonly, but requested "
                            f"with write access")
                else:
                    plugs[plug_spec['container_path']] = plug
            self._plugs: MutableMapping[str, Plug] = plugs

            # save actions
            state_action = result['state_action']
            if ('image' not in state_action or not state_action['image']) \
                    and ('entrypoint' not in state_action or not state_action['entrypoint']) \
                    and ('args' not in state_action or not state_action['args']):
                raise UserError(f"state action must not equal the default 'init' action (must have image, entrypoint, "
                                f"args, or a combination of some of those.")

            self._state_action: Action = \
                Action(work_dir=self._manifest.context.work_dir / self.name / "state",
                       name="state",
                       description=f"Discover state of resource '{self.name}'",
                       image=state_action['image'] if 'image' in state_action else self.type,
                       entrypoint=state_action['entrypoint'] if 'entrypoint' in state_action else None,
                       args=state_action['args'] if 'args' in state_action else None)

            # mark resource as initialized
            self._status: ResourceStatus = ResourceStatus.INITIALIZED

        self._plug_volumes: Sequence[str] = \
            [f"{p.path}:{cpath}:{'ro' if p.readonly else 'rw'}" for cpath, p in self._plugs.items()]
        volumes: list = []
        volumes.extend(self._docker_volumes)
        volumes.extend(self._plug_volumes)
        self._docker_invoker: DockerInvoker = DockerInvoker(volumes=volumes)

    def _resolve_state(self, logger: Logger) -> dict:

        # invoke the "state" action
        state_result = self._docker_invoker.run_json(
            logger=logger,
            local_work_dir=self._manifest.context.work_dir / self.name / self._state_action.name,
            container_work_dir=str(self._manifest.context.workspace_dir),
            image=self._state_action.image,
            entrypoint=self._state_action.entrypoint,
            args=self._state_action.args,
            input={
                'name': self.name,
                'type': self.type,
                'version': self._manifest.context.version,
                'verbose': self._manifest.context.verbose,
                'workspace': str(self._manifest.context.workspace_dir),
                'config': self._resolved_config
            }
        )

        # validate result against our the state schema
        try:
            jsonschema.validate(state_result, Resource.state_action_stdout_schema)
        except ValidationError as e:
            raise UserError(f"protocol error: '{self.name}' state result failed validation: {e.message}") from e

        return state_result

    def execute(self) -> None:

        # attempt to resolve all dependencies (resolving an already-resolved dependency has no side-effects)
        for dependency in self._dependencies.values():
            dependency.execute()

        # if we're already resolving, we have a circular dependency loop
        if self._status == ResourceStatus.RESOLVING:
            # TODO: print dependency chain
            raise UserError(f"illegal config: circular resource dependency encountered!")

        # if we were already resolved, do nothing (this can happen)
        elif self._status == ResourceStatus.VALID:
            return

        # fail if not initialized, or already resolving (circular dependency), and do nothing if already resolved
        elif self._status is None:
            raise Exception(f"internal error: cannot resolve un-initialized resource ('{self.name}')")

        with Logger(f":point_right: Inspecting {bold(self.name)} ({faint(self.type)})...") as logger:

            # post-process configuration
            config_context: dict = deepcopy(self._manifest.context.data)
            config_context.update({
                alias: {
                    'name': dep.name,
                    'type': dep.type,
                    'state': dep.state,
                } for alias, dep in self._dependencies.items()
            })
            self._resolved_config = post_process(value=self._config, context=config_context)

            # validate the config, now that it's been resolved
            try:
                jsonschema.validate(self._resolved_config, self._config_schema)
            except ValidationError as e:
                raise UserError(f"illegal config for '{self.name}.config.{'.'.join(e.path)}': {e.message}\n"
                                f"Must match schema: {e.schema}") from e

            # invoke the "state" action
            state_result = self._resolve_state(logger=logger)

            # save resource status
            self._status: ResourceStatus = ResourceStatus[state_result['status']]
            if self._status == ResourceStatus.VALID:
                self._state = state_result['state']
            elif self._status == ResourceStatus.STALE:

                # parse "apply" actions from the "state" action's response
                self._apply_actions = \
                    [Action(work_dir=self._manifest.context.work_dir / self.name / action['name'],
                            name=action['name'],
                            description=action['description'] if 'description' in action else action['name'],
                            image=action['image'] if 'image' in action else self.type,
                            entrypoint=action['entrypoint'] if 'entrypoint' in action else None,
                            args=action['args'] if 'args' in action else None) for action in state_result['actions']]

                if self._manifest.context.confirm == ConfirmationMode.RESOURCE:
                    if util.ask(logger=logger, message=bold('Execute this resource?'), chars='yn', default='n') == 'n':
                        raise UserError(f"user aborted")

                # execute the "apply" actions
                for action in self._apply_actions:
                    with Logger(header=f":wrench: {action.description} ({action.name})") as action_logger:

                        # confirm if necessary
                        if self._manifest.context.confirm == ConfirmationMode.ACTION:
                            if ask(logger=action_logger, message=bold('Execute?'), chars='yn', default='n') == 'n':
                                raise UserError(f"user aborted")

                        # execute
                        self._docker_invoker.run(
                            logger=action_logger,
                            local_work_dir=self._manifest.context.work_dir / self.name / action.name,
                            container_work_dir=str(self._manifest.context.workspace_dir),
                            image=action.image,
                            entrypoint=action.entrypoint,
                            args=action.args,
                            input={
                                'name': self.name,
                                'type': self.type,
                                'version': self._manifest.context.version,
                                'verbose': self._manifest.context.verbose,
                                'workspace': str(self._manifest.context.workspace_dir),
                                'config': self._resolved_config,
                                'staleState': state_result["staleState"] if "staleState" in state_result else {}
                            }
                        )
                        # TODO: consider refreshing state after every action?

                # verify that the resource is now VALID
                updated_state_result: dict = self._resolve_state(logger=logger)
                if ResourceStatus[updated_state_result['status']] != ResourceStatus.VALID:
                    raise UserError(f"protocol error: expected '{self.name}' to be VALID after applying actions")
                else:
                    self._status = ResourceStatus.VALID
                    self._state = updated_state_result['state']
            else:
                raise Exception(f"internal error: unrecognized status '{self._status}' for '{self.name}'")


class Plug:
    def __init__(self,
                 name: str,
                 path: str,
                 readonly: bool,
                 allowed_resource_names: Sequence[str],
                 allowed_resource_types: Sequence[str]):
        self._name: str = name
        self._path: Path = Path(os.path.expanduser(path=path)).absolute()
        self._readonly: bool = readonly
        self._resource_name_patterns: Sequence[Pattern] = [re.compile(name) for name in allowed_resource_names]
        self._resource_type_patterns: Sequence[Pattern] = [re.compile(type) for type in allowed_resource_types]

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
    def resource_name_patterns(self) -> Sequence[str]:
        return [re.pattern for re in self._resource_name_patterns]

    @property
    def resource_type_patterns(self) -> Sequence[str]:
        return [re.pattern for re in self._resource_type_patterns]

    def allowed_for(self, name: str, type: str) -> bool:
        for pattern in self._resource_name_patterns:
            if pattern.match(name):
                # matched a name pattern; allowed!
                return True
        for pattern in self._resource_type_patterns:
            if pattern.match(type):
                # matched a type pattern; allowed!
                return True
        # only allowed if this plug allows everything (ie. no name patterns and no type patterns)
        return not self._resource_name_patterns and not self._resource_type_patterns


class Manifest:
    schema = json.loads(pkgutil.get_data('schema', 'manifest.schema'))

    def __init__(self, context: Context, manifest_files: Sequence[Path],
                 resource_factory: Callable[..., Resource] = Resource) -> None:
        super().__init__()
        self._context = context
        self._manifest_files: Sequence[Path] = manifest_files

        composite_manifest: dict = {
            'plugs': {},
            'resources': {}
        }

        # read manifest files
        for manifest_file in self._manifest_files:
            with open(manifest_file, 'r') as f:
                # read the manifest
                try:
                    manifest = yaml.load(f.read())
                except yaml.YAMLError as e:
                    raise UserError(f"Manifest '{manifest_file}' is malformed: {e}") from e

                # validate the manifest
                try:
                    jsonschema.validate(manifest, Manifest.schema)
                except ValidationError as e:
                    raise UserError(f"Manifest '{manifest_file}' failed validation: {e.message}") from e

            # merge into the composite manifest
            if 'plugs' in manifest:
                for plug_name, plug in manifest['plugs'].items():
                    if plug_name in composite_manifest['plugs']:
                        raise UserError(f"Duplicate plug found: '{plug_name}'")
                    else:
                        composite_manifest['plugs'][plug_name] = plug
            if 'resources' in manifest:
                for resource_name, resource in manifest['resources'].items():
                    if resource_name in composite_manifest['resources']:
                        raise UserError(f"Duplicate resource found: '{resource_name}'")
                    else:
                        composite_manifest['resources'][resource_name] = resource

        # parse plugs
        plugs: MutableMapping[str, Plug] = {}
        for plug_name, plug in composite_manifest['plugs'].items():
            plug = post_process(value=plug, context=self.context.data)
            plugs[plug_name] = Plug(name=plug_name,
                                    path=plug['path'],
                                    readonly=plug['read_only'] if 'read_only' in plug else False,
                                    allowed_resource_names=plug['resource_names'] if 'resource_names' in plug else [],
                                    allowed_resource_types=plug['resource_types'] if 'resource_types' in plug else [])
        self._plugs: Mapping[str, Plug] = plugs

        # parse resources
        resources: MutableMapping[str, Resource] = {}

        def get_resource(name, data) -> Resource:
            if name in resources:
                return resources[name]

            dependencies: MutableMapping[str, Resource] = {}
            if 'dependencies' in data:
                for alias, dep_resource_name in data['dependencies'].items():
                    alias = post_process(alias, self.context.data)
                    dep_resource_name = post_process(dep_resource_name, self.context.data)
                    if dep_resource_name not in composite_manifest['resources']:
                        raise UserError(f"resource '{name}' depends on an unknown resource: {dep_resource_name}")
                    else:
                        dep_resource_data = composite_manifest['resources'][dep_resource_name]
                        dependencies[alias] = get_resource(dep_resource_name, dep_resource_data)
            resources[name] = \
                resource_factory(
                    manifest=self,
                    name=post_process(name, self.context.data),
                    type=post_process(data['type'], self.context.data),
                    readonly=post_process(data['readonly'], self.context.data) if 'readonly' in data else False,
                    config=data['config'] if 'config' in data else {},
                    dependencies=dependencies)
            return resources[name]

        for resource_name, resource in composite_manifest['resources'].items():
            get_resource(resource_name, resource)

        self._resources = resources

    @property
    def context(self) -> Context:
        return self._context

    def display_plugs(self) -> None:
        with Logger(header=f":electric_plug: {underline('Plugs:')}"):
            for name, value in self.plugs.items():
                with Logger(header=f":point_right: {name}: {bold(value.path)}", spacious=False):
                    if value.resource_name_patterns:
                        with Logger(header=f":heavy_exclamation_mark: Resource name patterns:", spacious=False) \
                                as names_logger:
                            for pattern in value.resource_name_patterns:
                                names_logger.info('- ' + pattern)
                    if value.resource_type_patterns:
                        with Logger(header=f":heavy_exclamation_mark: Resource type patterns:", spacious=False) \
                                as types_logger:
                            for pattern in value.resource_type_patterns:
                                types_logger.info('- ' + pattern)

    @property
    def manifest_files(self) -> Sequence[Path]:
        return self._manifest_files

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
