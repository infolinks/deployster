import json
import os
import pkgutil
import re
from pathlib import Path
from typing import Mapping, Sequence, Pattern, MutableMapping

import jinja2
import jsonschema
import yaml
from jinja2 import UndefinedError
from jsonschema import ValidationError

from context import Context
from util import log, UserError, bold, underline, indent, unindent


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

    def allowed_for(self, resource: Resource) -> bool:
        for pattern in self._resource_name_patterns:
            if pattern.match(resource.name):
                # matched a name pattern; allowed!
                return True
        for pattern in self._resource_type_patterns:
            if pattern.match(resource.type):
                # matched a type pattern; allowed!
                return True
        # only allowed if this plug allows everything (ie. no name patterns and no type patterns)
        return not self._resource_name_patterns and not self._resource_type_patterns


class Manifest:
    schema = json.loads(pkgutil.get_data('schema', 'manifest.schema'))

    def __init__(self, context: Context, manifest_files: Sequence[Path]) -> None:
        super().__init__()
        self._context = context
        self._manifest_files: Sequence[Path] = manifest_files

        # read manifest
        composite_manifest: dict = {
            'plugs': {},
            'resources': {}
        }
        for manifest_file in manifest_files:
            with open(manifest_file, 'r') as f:
                # TODO: load JSON manifests too (no reason why not, just use 'json.loads')
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
            plugs[plug_name] = Plug(name=plug_name,
                                    path=plug['path'],
                                    readonly=plug['read_only'] if 'read_only' in plug else False,
                                    allowed_resource_names=plug['resource_names'] if 'resource_names' in plug else [],
                                    allowed_resource_types=plug['resource_types'] if 'resource_types' in plug else [])
        self._plugs: Mapping[str, Plug] = plugs

        # parse resources
        resources: MutableMapping[str, Resource] = {}
        for resource_name, resource in composite_manifest['resources'].items():
            resources[resource_name] = \
                Resource(name=resource_name,
                         type=resource['type'],
                         readonly=resource['readonly'] if 'readonly' in resource else False,
                         config=resource['config'] if 'config' in resource else {},
                         dependencies=resource['dependencies'] if 'dependencies' in resource else {})
        self._resources = resources

    @property
    def context(self) -> Context:
        return self._context

    def display_plugs(self) -> None:
        log(bold(":paperclip: " + underline("Plugs:")))
        log('')
        indent()
        for name, value in self.plugs.items():
            log(f":point_right: {name}: {bold(value.path)}")
            if value.resource_name_patterns:
                indent()
                log(f"Resource name patterns:")
                indent()
                for pattern in value.resource_name_patterns:
                    log(pattern)
                unindent()
                unindent()
            if value.resource_type_patterns:
                indent()
                log(f"Resource type patterns:")
                indent()
                for pattern in value.resource_type_patterns:
                    log(pattern)
                unindent()
                unindent()

        unindent()
        log('')

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
