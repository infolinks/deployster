import argparse
import json
import subprocess
import sys
from abc import abstractmethod
from subprocess import PIPE
from time import sleep
from typing import Mapping, Sequence, Any, Callable, MutableSequence

from dresources import DResource, DAction, action
from gcp_gke_cluster import GkeCluster


class K8sResource(DResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)

        cfg = self.resource_config
        self._timeout: int = cfg['timeout'] if 'timeout' in cfg else 60
        self._timeout_interval: int = cfg['timeout_interval'] if 'timeout_interval' in cfg else 5

    @property
    @abstractmethod
    def cluster(self) -> GkeCluster:
        raise Exception(f"illegal state: 'cluster' reference not implemented for {type(self)} resource type")

    @property
    def namespace(self):
        return None

    @property
    def timeout(self) -> int:
        return self._timeout

    @property
    def timeout_interval(self) -> int:
        return self._timeout_interval

    @property
    @abstractmethod
    def k8s_api_group(self) -> str:
        raise Exception(f"illegal state: 'k8s_api_group' reference not implemented for {type(self)} resource type")

    @property
    @abstractmethod
    def k8s_api_version(self) -> str:
        raise Exception(f"illegal state: 'k8s_api_version' not implemented for {type(self)} resource type")

    @property
    @abstractmethod
    def k8s_kind(self) -> str:
        raise Exception(f"illegal state: 'k8s_kind' not implemented for {type(self)} resource type")

    @property
    def name(self) -> str:
        return self.k8s_manifest['metadata']['name']

    @property
    def k8s_manifest(self) -> dict:
        return self.resource_config['manifest']

    @property
    def resource_required_plugs(self) -> Mapping[str, str]:
        return {
            "gcloud": "/root/.config/gcloud"
        }

    @property
    def k8s_manifest_schema(self) -> dict:
        return {
            "type": "object",
            "required": ["metadata"],
            "additionalProperties": True,
            "properties": {
                "metadata": {
                    "type": "object",
                    "required": ["name"],
                    "additionalProperties": True,
                    "properties": {
                        "name": {"type": "string"},
                        "annotations": {
                            "type": "object",
                            "additionalProperties": True
                        },
                        "labels": {
                            "type": "object",
                            "additionalProperties": True
                        }
                    }
                }
            }
        }

    @property
    def resource_config_schema(self) -> dict:
        return {
            "type": "object",
            "required": ["manifest"],
            "additionalProperties": False,
            "properties": {
                "timeout": {"type": "integer"},
                "timeout_interval": {"type": "integer"},
                "manifest": self.k8s_manifest_schema
            }
        }

    def kubectl_command(self, verb, identify=True):
        if identify:
            namespace = f"--namespace {self.namespace.name}" if self.namespace is not None else ""
            return f"kubectl {verb} {self.k8s_kind} {self.name} {namespace}"
        else:
            return f"kubectl {verb}"

    def discover_actual_properties(self):
        process = subprocess.run(f"{self.kubectl_command('get')} --ignore-not-found=true --output=json",
                                 shell=True, check=True, stdout=PIPE, stderr=PIPE)
        return json.loads(process.stdout) if process.stdout else None

    def infer_actions_from_actual_properties(self, actual_properties: dict) -> Sequence[DAction]:
        desired_metadata = self.k8s_manifest['metadata']
        desired_anns = desired_metadata['annotations'] if 'annotations' in desired_metadata else {}
        desired_labels = desired_metadata['labels'] if 'labels' in desired_metadata else {}
        actual_metadata = actual_properties['metadata']
        actual_anns = actual_metadata['annotations'] if 'annotations' in actual_metadata else {}
        actual_labels = actual_metadata['labels'] if 'labels' in actual_metadata else {}

        # add an action for each stale annotation & label
        actions: MutableSequence[DAction] = []
        actions.extend([DAction(name='update-ann',
                                description=f"Update annotation '{k}' to '{v}'",
                                args=['update_annotation', k, v])
                        for k, v in desired_anns.items() if k not in actual_anns or v != actual_anns[k]])
        actions.extend([DAction(name='update-label',
                                description=f"Update label '{k}' to '{v}'",
                                args=['update_label', k, v])
                        for k, v in desired_labels.items() if k not in actual_labels or v != actual_labels[k]])
        return actions

    @property
    def actions_for_missing_status(self) -> Sequence[DAction]:
        return [DAction(name='create', description=f"Create {self.k8s_kind.lower()} '{self.name}'")]

    def build_creation_manifest(self) -> dict:
        api_group = self.k8s_api_group
        api_version = self.k8s_api_version
        manifest = {
            "apiVersion": f"{api_group}/{api_version}" if api_group != 'core' else api_version,
            "kind": self.k8s_kind
        }
        manifest.update(self.k8s_manifest)
        if self.namespace is not None:
            if 'metadata' not in manifest:
                manifest['metadata'] = {}
            # noinspection PyUnresolvedReferences
            manifest['metadata']['namespace'] = self.namespace.name
        return manifest

    def is_available(self, actual_properties: dict):
        if actual_properties: pass
        return True

    def wait_for_availability(self, availability_validator: Callable[[dict], bool] = None) -> bool:
        if availability_validator is None:
            availability_validator = self.is_available

        waited = 0
        while waited < self.timeout:
            actual_properties = self.discover_actual_properties()
            if actual_properties is not None and availability_validator(actual_properties):
                return True
            else:
                sleep(self.timeout_interval)
                waited = waited + self.timeout_interval
        return False

    @action
    def create(self, args) -> None:
        if args: pass

        subprocess.run(f"{self.kubectl_command('create', identify=False)} -f -",
                       input=json.dumps(self.build_creation_manifest()).encode('utf-8'),
                       check=True,
                       timeout=self.timeout,
                       shell=True)

        if not self.wait_for_availability():
            print(f"{self.k8s_kind} '{self.name}' was not created successfully.\n"
                  f"Use this command to find out more:\n"
                  f"    {self.kubectl_command('get')}",
                  file=sys.stderr)
            exit(1)

    @action
    def update_annotation(self, args) -> None:
        subprocess.run(f"{self.kubectl_command('annotate')} --overwrite {args.name}='{args.value}'",
                       check=True,
                       timeout=self.timeout,
                       shell=True)

    @action
    def update_label(self, args) -> None:
        subprocess.run(f"{self.kubectl_command('label')} --overwrite {args.name}='{args.value}'",
                       check=True,
                       timeout=self.timeout,
                       shell=True)

    def execute_action(self, action_name: str, action_method: Callable[..., Any], args: argparse.Namespace) -> None:
        if action_name != 'init':
            self.cluster.authenticate()
        super().execute_action(action_name, action_method, args)
