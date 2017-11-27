import argparse
import json
import subprocess
import sys
from abc import abstractmethod
from copy import deepcopy
from subprocess import PIPE
from time import sleep
from typing import Sequence, MutableSequence, Mapping, Any

from dresources import DAction, action, DResource
from gcp_gke_cluster import GkeCluster


class K8sResource(DResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.add_plug(name='kube', container_path='/root/.kube', optional=False, writable=False)
        self.config_schema.update({
            "required": ["manifest"],
            "additionalProperties": True,
            "properties": {
                "timeout": {"type": "integer"},
                "timeout_interval": {"type": "integer"},
                "manifest": {
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
            }
        })

    @property
    @abstractmethod
    def cluster(self) -> GkeCluster:
        raise Exception(f"illegal state: 'cluster' not implemented for '{type(self).__name__}'")

    @property
    def namespace(self):
        return None

    @property
    def timeout(self) -> int:
        return self.resource_config['timeout'] if 'timeout' in self.resource_config else 60 * 5

    @property
    def timeout_interval(self) -> int:
        return self.resource_config['timeout_interval'] if 'timeout_interval' in self.resource_config else 5

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
    def k8s_manifest(self) -> Mapping[str, Any]:
        return self.resource_config['manifest']

    @property
    def metadata(self) -> Mapping[str, Any]:
        return self.k8s_manifest['metadata']

    @property
    def name(self) -> str:
        return self.metadata['name']

    @property
    def annotations(self) -> Mapping[str, str]:
        return self.metadata['annotations'] if 'annotations' in self.metadata else {}

    @property
    def labels(self) -> Mapping[str, str]:
        return self.metadata['labels'] if 'labels' in self.metadata else {}

    def kubectl_command(self, verb):
        namespace = f" --namespace {self.namespace.name}" if self.namespace is not None else ""
        return f"kubectl {verb} {self.k8s_kind} {self.name}{namespace}"

    def discover_actual_properties(self):
        process = subprocess.run(f"{self.kubectl_command('get')} --ignore-not-found=true --output=json",
                                 shell=True, check=True, stdout=PIPE)
        return json.loads(process.stdout) if process.stdout else None

    def get_actions_when_missing(self) -> Sequence[DAction]:
        return [DAction(name='create', description=f"Create {self.k8s_kind.lower()} '{self.name}'")]

    def get_actions_when_existing(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = []

        actual_metadata = actual_properties['metadata']
        actual_anns = actual_metadata['annotations'] if 'annotations' in actual_metadata else {}
        actual_labels = actual_metadata['labels'] if 'labels' in actual_metadata else {}

        # add an action for each stale annotation
        actions.extend([
            DAction(name='update-annotation',
                    description=f"Update annotation '{k}' to '{v}'",
                    args=['update_annotation', k, v])
            for k, v in self.annotations.items() if k not in actual_anns or v != actual_anns[k]
        ])

        # add an action for each stale label
        actions.extend([
            DAction(name='update-label',
                    description=f"Update label '{k}' to '{v}'",
                    args=['update_label', k, v])
            for k, v in self.labels.items() if k not in actual_labels or v != actual_labels[k]
        ])

        return actions

    def define_action_args(self, action: str, argparser: argparse.ArgumentParser):
        super().define_action_args(action, argparser)
        if action == 'update_annotation':
            argparser.add_argument('name', help='annotation name')
            argparser.add_argument('value', help='annotation value')
        elif action == 'update_label':
            argparser.add_argument('name', help='label name')
            argparser.add_argument('value', help='label value')

    def build_creation_manifest(self) -> dict:
        api_group = self.k8s_api_group
        api_version = self.k8s_api_version
        manifest = {
            "apiVersion": f"{api_group}/{api_version}" if api_group != 'core' else api_version,
            "kind": self.k8s_kind
        }
        manifest.update(deepcopy(self.k8s_manifest))
        if self.namespace is not None:
            if 'metadata' not in manifest:
                manifest['metadata'] = {}
            # noinspection PyUnresolvedReferences
            manifest['metadata']['namespace'] = self.namespace.name
        return manifest

    def check_availability(self, actual_properties: dict):
        if actual_properties: pass
        return True

    def wait_for_availability(self) -> bool:
        waited = 0
        while waited < self.timeout:
            actual_properties = self.discover_actual_properties()
            if actual_properties is not None and self.check_availability(actual_properties):
                return True
            else:
                sleep(self.timeout_interval)
                waited = waited + self.timeout_interval
        return False

    @action
    def create(self, args) -> None:
        if args: pass

        subprocess.run(f"kubectl create -f -",
                       input=json.dumps(self.build_creation_manifest()),
                       encoding='utf-8',
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
