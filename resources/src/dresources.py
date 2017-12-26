import argparse
import json
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Mapping, Sequence, Any, Callable, MutableMapping

from external_services import ExternalServices


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

    @property
    def name(self) -> str:
        """The resource name, as depicted by the user in the deployment manifest."""
        return self._data['name']

    @property
    def type(self) -> str:
        """The resource type. This is the resource's Docker image."""
        return self._data['type']

    @property
    def deployster_version(self) -> str:
        return self._data['version']

    @property
    def verbose(self) -> bool:
        return self._data['verbose']

    @property
    def workspace(self) -> Path:
        return Path(self._data['workspace'])

    @property
    def has_config(self)->bool:
        return 'config' in self._data

    @property
    def config(self) -> Mapping[str, Any]:
        """The resource configuration, which in essence is the *desired* state of the resource, as depicted by the user
        in the deployment manifest."""
        return self._data['config']

    @property
    def stale_state(self) -> dict:
        return self._data['staleState']


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

    def __init__(self, data: dict, svc: ExternalServices) -> None:
        super().__init__()
        self._info = DResourceInfo(data)
        self._svc: ExternalServices = svc
        self._plugs: MutableMapping[str, DPlug] = {}
        self._config_schema = {
            "type": "object",
            "additionalProperties": True,
            "properties": {}
        }

    @property
    def svc(self) -> ExternalServices:
        return self._svc

    @property
    def info(self) -> DResourceInfo:
        return self._info

    def get_plug(self, name: str) -> DPlug:
        return self._plugs[name]

    def add_plug(self, name: str, container_path: str, optional: bool, writable: bool):
        """Signals that this resource requests or demands this plug."""
        self._plugs[name] = DPlug(container_path=container_path, optional=optional, writable=writable)

    @property
    def config_schema(self) -> dict:
        """Provides the JSON schema to be used to validate resource configuration in the manifest.

        The default schema only validates that the configuration is an object. You can modify the returned dict."""
        return self._config_schema

    @abstractmethod
    def discover_state(self):
        """Discovers the resource's actual properties, as they currently deployed.

        This method must be implemented by subclasses, and either return a dictionary describing the resource, or, if
        the resource is not found, return None."""
        raise NotImplementedError(f"internal error: 'discover_state' not implemented")  # pragma: no cover

    @abstractmethod
    def get_actions_for_missing_state(self) -> Sequence[DAction]:
        """Provides the list of actions to invoke when the resource is MISSING.

        Must be implemented by subclasses. It will be called when the "discover_actual_properties" method returns
        None."""
        raise NotImplementedError(
            f"internal error: 'get_actions_for_missing_state' not implemented")  # pragma: no cover

    @abstractmethod
    def get_actions_for_discovered_state(self, state: dict) -> Sequence[DAction]:
        """Provides the list of actions to invoke when the resource *was* found.

        Must be implemented by subclasses. It will be called when the "discover_actual_properties" method DOES NOT
        return None.

        This method can return an empty list, signaling in essence that the resource is VALID."""
        raise NotImplementedError(
            f"internal error: 'get_actions_for_discovered_state' not implemented")  # pragma: no cover

    # noinspection PyUnusedLocal
    def configure_action_argument_parser(self, action: str, argparser: argparse.ArgumentParser):
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
        print(json.dumps({
            "plugs": {plug_name: plug.to_dict() for plug_name, plug in plugs.items()},
            "config_schema": self.config_schema,
            "state_action": {
                "args": ["state"]
            }
        }))

    @action
    def state(self, args) -> None:
        if args: pass
        state: dict = self.discover_state()
        if state is not None:
            actions: Sequence[DAction] = self.get_actions_for_discovered_state(state=state)
            if actions:
                print(json.dumps({
                    'status': 'STALE',
                    'staleState': state,
                    'actions': [action.to_dict() for action in actions]
                }, indent=2))
            else:
                print(json.dumps({
                    'status': 'VALID',
                    'state': state
                }, indent=2))
        else:
            print(json.dumps({
                'status': 'STALE',
                'actions': [action.to_dict() for action in self.get_actions_for_missing_state()]
            }, indent=2))

    def execute_action(self, action_name: str,
                       action_method: Callable[['DResource', argparse.Namespace], None],
                       args: argparse.Namespace):
        if action_name: pass
        action_method(self, args)

    def execute(self, args=sys.argv[1:]) -> None:
        argparser: argparse.ArgumentParser = argparse.ArgumentParser(description=f"Resource {self.info.name}")
        subparsers = argparser.add_subparsers()

        inspection_target = type(self)
        for attr_name in dir(inspection_target):
            attr: Any = getattr(inspection_target, attr_name)
            if callable(attr):
                method: function = attr
                if hasattr(method, 'action'):
                    parser = subparsers.add_parser(method.__name__)
                    self.configure_action_argument_parser(method.__name__, parser)
                    parser.set_defaults(action_name=method.__name__, action_method=method)

        args = argparser.parse_args(args=args)
        self.execute_action(args.action_name, args.action_method, args)
