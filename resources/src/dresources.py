import argparse
import json
from abc import ABC, abstractmethod
from typing import Mapping, Sequence, Any, Callable, MutableSequence, MutableMapping


def action(fun):
    """Method decorator signaling to Deployster Python wrapper that this method is a resource action."""
    # TODO: validate function has single 'args' argument (using 'inspect.signature(fun)')
    fun.action = True
    return fun


class DAction:
    """
    Deployster action descriptor.

    Resources return a list of actions as part of their response from the 'state' action.
    """

    def __init__(self,
                 name: str = None,
                 description: str = None,
                 image: str = None,
                 entrypoint: str = None,
                 args: Sequence[str] = None) -> None:
        super().__init__()
        self._name: str = name
        self._description: str = description
        self._image: str = image
        self._entrypoint: str = entrypoint
        self._args: Sequence[str] = args if args is not None else [self._name.replace('-', '_')]

    @property
    def name(self) -> str:
        """The action name."""
        return self._name

    @property
    def description(self) -> str:
        """Short description of the action, possibly shown the user."""
        return self._description

    @property
    def image(self) -> str:
        """The Docker image to run to execute this action. Does not have to be the same image of the resource that
        provides the action, but it usually is."""
        return self._image

    @property
    def entrypoint(self) -> str:
        """The entrypoint used when executing the action Docker image. If not provided, the Docker image's default
        entrypoint will be executed."""
        return self._entrypoint

    @property
    def args(self) -> Sequence[str]:
        """Optional arguments to pass to the Docker image's entrypoint."""
        return self._args

    def to_dict(self) -> dict:
        """Converts the action into a dictionary that can be serialized (usually as JSON) back to Deployster."""
        data: dict = {}
        if self.name: data['name'] = self.name
        if self.description: data['description'] = self.description
        if self.image: data['image'] = self.image
        if self.entrypoint: data['entrypoint'] = self.entrypoint
        if self.args: data['args'] = self.args
        return data


class DPlug:
    """
    Describes a plug that a resource requests (or demands).

    Each resource can requested or demand a set of plugs that allow it to communicate back to Deployster, other
    resources, or even back to the user.

    Each plug is essentially a mounted volume that Deployster provides to the
    resource Docker image from the host machine. The resource can then read or write information to/from the volume. In
    turn, that plug is usually "plugged" into additional resources, enabling cross-resource communication.

    Common use-cases include providing GCP service account JSON files as plugs, shared directories for storing data
    that's used by multiple resources, etc.
    """

    def __init__(self, container_path: str, optional: bool, writable: bool) -> None:
        super().__init__()
        self._container_path: str = container_path
        self._optional: bool = optional
        self._writable: bool = writable

    @property
    def container_path(self) -> str:
        """The path to mount the plug in the resource Docker image when plugged into the resource."""
        return self._container_path

    @property
    def optional(self) -> bool:
        """Whether the resource can work without the plug, or whether the it's required for the resource to function."""
        return self._optional

    @property
    def writable(self) -> bool:
        """Whether the plug must be writable for the resource to function, or if it can be a readonly plug."""
        return self._writable

    def to_dict(self) -> dict:
        """Converts the plug descriptor to a dictionary for serialization back to Deployster (usually as JSON)."""
        return {'container_path': self.container_path, 'optional': self.optional, 'writable': self.writable}


class DResourceInfo:
    """Provides the raw resource information provided by Deployster. Each resource receives (on stdin) everything that
    Deployster knows about the resource, which includes:

    - the resource name
    - the resource type (its Docker image)
    - the resource configuration (everything under the 'config' property of the resource in the manifest)
    - dependency information: set of named dependencies that the user wired to the resource
    - optional actual state (properties) of the resource, as previously discovered for the resource in its state action
    """

    def __init__(self, data: dict) -> None:
        super().__init__()
        self._data = data
        self._name = data['name']
        self._type = data['type']
        self._config: dict = data['config']
        self._dependencies: dict = data['dependencies'] if 'dependencies' in data else None
        self._properties = data['properties'] if 'properties' in data else None

    @property
    def name(self) -> str:
        """The resource name, as depicted by the user in the deployment manifest."""
        return self._name

    @property
    def type(self) -> str:
        """The resource type. This is the resource's Docker image."""
        return self._type

    @property
    def config(self) -> Mapping[str, Any]:
        """The resource configuration, which in essence is the *desired* state of the resource, as depicted by the user
        in the deployment manifest."""
        return self._config

    @property
    def dependencies(self) -> Mapping[str, dict]:
        """The set of dependencies that the user wired to this resource. This provides a mapping between a dependency
        resource's name, and the same set of information for the dependency, as provided for this resource.

        So for each dependency, a dictionary containing the name, type, configuration, dependencies and so on will be
        provided. This is recursive (ie. each dependency can have its own dependencies, etc) and circular dependencies
        have been resolved by Deployster prior to this information being provided."""
        return self._dependencies

    @property
    def properties(self) -> dict:
        """If the resource already calculated its *actual* state, it will be provided on subsequent invocation."""
        return self._properties


class Dependency:

    def __init__(self, resource_info: DResourceInfo, name: str, type: str, optional: bool, factory: type) -> None:
        super().__init__()
        self._resource_info = resource_info
        self._name = name
        self._type = type
        self._optional = optional
        self._factory = factory
        self._instance = None

    @property
    def resource_info(self) -> DResourceInfo:
        return self._resource_info

    @property
    def name(self) -> str:
        return self._name

    @property
    def type(self) -> str:
        return self._type

    @property
    def optional(self) -> bool:
        return self._optional

    @property
    def factory(self) -> type:
        return self._factory

    @property
    def instance(self) -> Any:
        if self._instance:
            return self._instance
        elif self.name in self.resource_info.dependencies:
            data = self.resource_info.dependencies[self.name]
            self._instance = self.factory(data)
            return self._instance
        elif self.optional:
            return None
        else:
            # this should not happen, since Deployster is supposed to validate this for us
            raise Exception(f"required dependency '{self.name}' is missing")

    def to_dict(self) -> dict:
        """Converts the dependency to a dictionary for serialization back to Deployster (usually as JSON)."""
        return {'type': self.type, 'optional': self.optional}


# noinspection PyTypeChecker
class DResource(ABC):
    """
    Deployster resource base class.

    This class serves as a base class for Deployster resource implementations. It handles most of the heavy lifting of
    creating a resource by handling the resource lifecycle:

    - execution: parsing command line arguments, determining the correct "action", etc
    - initialization (the "init" action)
    - state calculation (the "state" action)
    - dependency handling
    """

    def __init__(self, data: dict) -> None:
        super().__init__()
        self._info = DResourceInfo(data)
        self._plugs: MutableSequence[str, DPlug] = {}
        self._dependencies: MutableMapping[str, Dependency] = {}
        self._config_schema = {
            "type": "object",
            "additionalProperties": True,
            "properties": {}
        }

    @property
    def resource_name(self) -> str:
        """Provides the resource's name, as depicted in the deployment manifest."""
        return self._info.name

    @property
    def resource_config(self) -> Mapping[str, Any]:
        """Provides the resource configuration as provided in the deployment manifest."""
        return self._info.config

    @property
    def resource_properties(self) -> Mapping[str, Any]:
        """Provides the resource actual properties.

        This is in essence the actual state of the resource, but is only available if previously calculated by this
        resource, and subsequently provided by Deployster."""
        return self._info.config

    def get_plug(self, name: str) -> DPlug:
        return self._plugs[name]

    def add_plug(self, name: str, container_path: str, optional: bool, writable: bool):
        """Signals that this resource requests or demands this plug."""
        self._plugs[name] = DPlug(container_path=container_path, optional=optional, writable=writable)

    def add_dependency(self, name: str, type: str, optional: bool, factory: type):
        """Signals that this resource requests or demands the given resource dependency."""
        self._dependencies[name] = \
            Dependency(resource_info=self._info, name=name, type=type, optional=optional, factory=factory)

    @property
    def config_schema(self) -> dict:
        """Provides the JSON schema to be used to validate resource configuration in the manifest.

        By default, only validates that the configuration is an object."""
        return self._config_schema

    def get_dependency(self, name: str) -> Any:
        """Provides the requested dependency instance."""
        if name not in self._dependencies:
            raise Exception(f"illegal state: dependency '{name}' was requested by a DResource, but was not declared")

        dependency = self._dependencies[name]
        return dependency.instance

    @abstractmethod
    def discover_actual_properties(self):
        """Discovers the resource's actual properties, as they currently deployed.

        This method must be implemented by subclasses, and either return a dictionary describing the resource, or, if
        the resource is not found, return None."""
        raise Exception(f"illegal state: 'discover_actual_properties' not implemented")

    @abstractmethod
    def get_actions_when_missing(self) -> Sequence[DAction]:
        """Provides the list of actions to invoke when the resource is MISSING.

        Must be implemented by subclasses. It will be called when the "discover_actual_properties" method returns
        None."""
        raise Exception(f"illegal state: 'get_actions_when_missing' not implemented")

    @abstractmethod
    def get_actions_when_existing(self, actual_properties: dict) -> Sequence[DAction]:
        """Provides the list of actions to invoke when the resource *was* found.

        Must be implemented by subclasses. It will be called when the "discover_actual_properties" method DOES NOT
        return None.

        This method can return an empty list, signaling in essence that the resource is VALID."""
        raise Exception(f"illegal state: 'get_actions_when_existing' not implemented")

    def define_action_args(self, action: str, argparser: argparse.ArgumentParser):
        """Called to configure the argument parser for the given action.

        SHOULD be implemented by subclasses to support actions that require command line arguments. Those arguments will
        be supplied by Deployster if specified for the action in its "args" array."""
        if action == 'init':
            pass
        elif action == 'state':
            pass

    @action
    def init(self, args) -> None:
        """This is the "init" action, usually set as the default entrypoint of the resource."""
        if args: pass

        plugs: dict = self._plugs
        dependencies: Sequence[Dependency] = self._dependencies.values()
        print(json.dumps({
            "plugs": {plug_name: plug.to_dict() for plug_name, plug in plugs.items()},
            "dependencies": {dep.name: dep.to_dict() for dep in dependencies},
            "config_schema": self.config_schema,
            "state_action": {
                "name": "state",
                "description": f"Calculates state for resource '{self.resource_name}'",
                "args": ["state"]
            }
        }))

    @action
    def state(self, args) -> None:
        if args: pass
        actual_properties: dict = self.discover_actual_properties()
        if actual_properties is not None:
            actions: Sequence[DAction] = self.get_actions_when_existing(actual_properties=actual_properties)
            if actions:
                print(json.dumps({
                    'status': 'STALE',
                    'actions': [action.to_dict() for action in actions],
                    'staleProperties': actual_properties
                }, indent=2))
            else:
                print(json.dumps({
                    'status': 'VALID',
                    'properties': actual_properties
                }, indent=2))
        else:
            print(json.dumps({
                'status': 'MISSING',
                'actions': [action.to_dict() for action in self.get_actions_when_missing()]
            }, indent=2))

    def execute_action(self, action_name: str, action_method: Callable[..., Any], args: argparse.Namespace):
        if action_name: pass
        action_method(self, args)

    def execute(self) -> None:
        argparser: argparse.ArgumentParser = argparse.ArgumentParser(description=f"Resource {self.resource_name}")
        subparsers = argparser.add_subparsers()

        inspection_target = type(self)
        for attr_name in dir(inspection_target):
            attr: Any = getattr(inspection_target, attr_name)
            if callable(attr):
                method: function = attr
                if hasattr(method, 'action'):
                    parser = subparsers.add_parser(method.__name__)
                    self.define_action_args(method.__name__, parser)
                    parser.set_defaults(action_name=method.__name__, action_method=method)

        args = argparser.parse_args()
        self.execute_action(args.action_name, args.action_method, args)


def collect_differences(desired: Any, actual: Any,
                        path: MutableSequence[str] = None, diffs: MutableSequence[str] = None):
    diffs = [] if diffs is None else diffs
    path = [] if path is None else path
    if (desired is not None and actual is None) or (desired is None and actual is not None):
        diffs.append(".".join(path))
    elif desired is None and actual is None:
        pass
    elif type(desired) != type(actual):
        diffs.append(".".join(path))
    elif desired is not None and actual is not None:
        if isinstance(desired, dict):
            for key, desired_value in desired.items():
                path.append(key)
                try:
                    if actual is None or key not in actual:
                        diffs.append(".".join(path))
                        continue
                    actual_value = actual[key]
                    collect_differences(desired_value, actual_value, path, diffs)
                finally:
                    path.pop()

        elif isinstance(desired, list):
            if len(desired) != len(actual):
                diffs.append(".".join(path))
            else:
                for index, desired_value in enumerate(desired):
                    actual_value = actual[index]
                    path.append(f"[{index}]")
                    try:
                        collect_differences(desired_value, actual_value, path, diffs)
                    finally:
                        path.pop()
        elif desired != actual:
            diffs.append(".".join(path))
    else:
        raise Exception(f"illegal state")
    return diffs
