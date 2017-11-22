import argparse
import json
from abc import ABC, abstractmethod
from typing import Mapping, Sequence, Any, Callable


def action(fun):
    """Method decorator signaling to Deployster Python wrapper that this method is a resource action."""
    # TODO: validate function has single 'args' argument
    fun.action = True
    return fun


class DAction:
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

    def to_dict(self) -> dict:
        data: dict = {}
        if self.name: data['name'] = self.name
        if self.description: data['description'] = self.description
        if self.image: data['image'] = self.image
        if self.entrypoint: data['entrypoint'] = self.entrypoint
        if self.args: data['args'] = self.args
        return data


class DResource(ABC):
    def __init__(self, data: dict) -> None:
        super().__init__()
        self._data = data
        self._resource_name = data['name']
        self._resource_type = data['type']
        self._resource_config: dict = data['config']
        self._resource_properties = data['properties'] if 'properties' in data else None

    @property
    def resource_name(self) -> str:
        return self._resource_name

    @property
    def resource_type(self) -> str:
        return self._resource_type

    @property
    def resource_type_label(self) -> str:
        return self.resource_type

    @property
    def resource_config(self) -> dict:
        return self._resource_config

    @property
    def resource_properties(self) -> dict:
        return self._resource_properties

    def resource_dependency(self, name: str) -> dict:
        if 'dependencies' not in self._data:
            raise Exception(f"illegal state: dependency lookup cannot be used during resource initialization")

        dependencies_data: dict = self._data['dependencies']
        if name not in dependencies_data:
            raise Exception(f"illegal state: dependency '{name}' was not provided")

        return dependencies_data[name]

    @property
    def resource_required_plugs(self) -> Mapping[str, str]:
        return {}

    @property
    def resource_required_resources(self) -> Mapping[str, str]:
        return {}

    @property
    @abstractmethod
    def resource_config_schema(self) -> Mapping[str, dict]:
        raise Exception(f"illegal state: 'resource_config_schema' not implemented")

    @abstractmethod
    def discover_actual_properties(self):
        raise Exception(f"illegal state: 'discover_actual_properties' not implemented")

    @abstractmethod
    def infer_actions_from_actual_properties(self, actual_properties: dict) -> Sequence[DAction]:
        raise Exception(f"illegal state: 'infer_actions_from_actual_properties' not implemented")

    @property
    @abstractmethod
    def actions_for_missing_status(self) -> Sequence[DAction]:
        raise Exception(f"illegal state: 'actions_for_missing_status' not implemented")

    def define_action_args(self, action: str, argparser: argparse.ArgumentParser):
        if action == 'init':
            pass
        elif action == 'state':
            pass

    @action
    def init(self, args) -> None:
        if args: pass
        print(json.dumps({
            "label": self.resource_type_label,
            "required_resources": self.resource_required_resources,
            "required_plugs": self.resource_required_plugs,
            "config_schema": self.resource_config_schema,
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
        if actual_properties:
            actions: Sequence[DAction] = self.infer_actions_from_actual_properties(actual_properties=actual_properties)
            if actions:
                print(json.dumps({'status': 'STALE', 'actions': [action.to_dict() for action in actions]}, indent=2))
            else:
                print(json.dumps({'status': 'VALID', 'properties': actual_properties}, indent=2))
        else:
            print(json.dumps({
                'status': 'MISSING',
                'actions': [action.to_dict() for action in self.actions_for_missing_status]
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
