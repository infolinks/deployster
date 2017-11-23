import argparse
import json
import subprocess
import sys
from abc import abstractmethod
from time import sleep
from typing import MutableSequence, Mapping, Sequence, Any, Callable

from dresources import DResource, DAction, action
from gcp_gke_cluster import GkeCluster


class K8sResource(DResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self._metadata: Mapping[str, Any] = \
            self.resource_config['metadata'] if 'metadata' in self.resource_config else {}
        self._annotations: Mapping[str, Any] = self._metadata['annotations'] if 'annotations' in self._metadata else {}
        self._labels: Mapping[str, str] = self._metadata['labels'] if 'labels' in self._metadata else {}
        self._timeout: int = self.resource_config['timeout'] if 'timeout' in self.resource_config else 60
        self._timeout_interval: int = \
            self.resource_config['timeout_interval'] if 'timeout_interval' in self.resource_config else 5

    @property
    def timeout(self) -> int:
        return self._timeout

    @property
    def timeout_interval(self) -> int:
        return self._timeout_interval

    @property
    @abstractmethod
    def cluster(self) -> GkeCluster:
        raise Exception(f"illegal state: 'cluster' reference not implemented for {type(self)} resource type")

    @property
    def namespace(self):
        return None

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
    @abstractmethod
    def name(self) -> str:
        raise Exception(f"illegal state: 'name' not implemented for {type(self)} resource type")

    @property
    def metadata(self) -> Mapping[str, Any]:
        return self._metadata

    @property
    def annotations(self) -> Mapping[str, Any]:
        return self._annotations

    @property
    def labels(self) -> Mapping[str, str]:
        return self._labels

    @property
    def resource_required_plugs(self) -> Mapping[str, str]:
        return {
            "gcloud": "/root/.config/gcloud"
        }

    @property
    def resource_config_schema(self) -> dict:
        return {
            "type": "object",
            "required": ["name"],
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string"},
                "timeout": {"type": "integer"},
                "metadata": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "annotations": {"type": "object"},
                        "labels": {"type": "object"}
                    }
                }
            }
        }

    def discover_actual_properties(self):
        namespace_arg = f"--namespace {self.namespace.name}" if self.namespace is not None else ""
        command = f"kubectl get {self.k8s_kind.lower()} {self.name} {namespace_arg} --ignore-not-found=true -o json"
        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode != 0:
            raise Exception(f"illegal state: failed getting {self.k8s_kind.lower()} '{self.name}':\n{process.stderr}")
        else:
            return json.loads(process.stdout) if process.stdout else None

    def infer_actions_from_actual_properties(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = []

        # compare
        actual_metadata = actual_properties['metadata'] if 'metadata' in actual_properties else {}

        # compare annotations
        actual_annotations = actual_metadata['annotations'] if 'annotations' in actual_metadata else {}
        for ann_name, ann_value in self.annotations.items():
            if ann_name not in actual_annotations or ann_value != actual_annotations[ann_name]:
                actions.append(DAction(name='update-annotation',
                                       description=f"Update annotation '{ann_name}'",
                                       args=['update_annotation', ann_name, ann_value]))

        # compare labels
        actual_labels = actual_metadata['labels'] if 'labels' in actual_metadata else {}
        for label_name, label_value in self.labels.items():
            if label_name not in actual_labels or label_value != actual_labels[label_name]:
                actions.append(DAction(name='update-label',
                                       description=f"Update label '{label_name}'",
                                       args=['update_label', label_name, label_value]))

        # if any actions inferred, we're STALE; otherwise we're VALID
        return actions

    @property
    def actions_for_missing_status(self) -> Sequence[DAction]:
        return [DAction(name='create', description=f"Create {self.k8s_kind.lower()} '{self.name}'")]

    def define_action_args(self, action: str, argparser: argparse.ArgumentParser) -> None:
        super().define_action_args(action, argparser)
        if action == 'update_annotation':
            argparser.add_argument('name', metavar='NAME', help="name of the annotation to set")
            argparser.add_argument('value', metavar='VALUE', help="value for the annotation")
        elif action == 'update_label':
            argparser.add_argument('name', metavar='NAME', help="name of the label to set")
            argparser.add_argument('value', metavar='VALUE', help="value for the label")

    def build_manifest(self) -> dict:
        api_version = \
            f"{self.k8s_api_group}/{self.k8s_api_version}" if self.k8s_api_group != 'core' else self.k8s_api_version
        manifest = {
            "apiVersion": api_version,
            "kind": self.k8s_kind,
            "metadata": {
                "name": self.name,
                "annotations": self.annotations,
                "labels": self.labels
            }
        }
        if self.namespace is not None:
            manifest['metadata']['namespace'] = self.namespace.name
        return manifest

    @action
    def create(self, args) -> None:
        manifest = self.build_manifest()
        print(json.dumps(manifest, indent=2), file=sys.stderr)

        filename = f"/tmp/resource-{self.name}.json"
        with open(filename, 'w') as f:
            f.write(json.dumps(manifest))
        command = f"kubectl create --output=json --filename={filename}"
        subprocess.run(command, check=True, timeout=self.timeout, shell=True)

    @action
    def update_annotation(self, args) -> None:
        namespace_arg = f"--namespace {self.namespace.name}" if self.namespace is not None else ""

        name = args.name
        value = args.value
        command = f"kubectl annotate {self.k8s_kind.lower()} {self.name} {namespace_arg} {name}='{value}' --overwrite"
        subprocess.run(command, check=True, timeout=self.timeout, shell=True)

    @action
    def update_label(self, args) -> None:
        namespace_arg = f"--namespace {self.namespace.name}" if self.namespace is not None else ""

        name = args.name
        value = args.value
        command = f"kubectl label {self.k8s_kind.lower()} {self.name} {namespace_arg} {name}='{value}' --overwrite"
        subprocess.run(command, check=True, timeout=self.timeout, shell=True)

    def execute_action(self, action_name: str, action_method: Callable[..., Any], args: argparse.Namespace) -> None:
        if action_name != 'init':
            self.cluster.authenticate()
        super().execute_action(action_name, action_method, args)

    def wait_for_resource(self, status_validator: Callable[[dict], bool]) -> bool:
        namespace_arg = f"--namespace {self.namespace.name}" if self.namespace is not None else ""
        waited = 0
        while waited < self.timeout:
            command = f"kubectl get {self.k8s_kind.lower()} {self.name} {namespace_arg} -o json"
            process = subprocess.run(command, check=False, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if process.returncode != 0:
                print(f"failed polling for {self.k8s_kind.lower()} status:\n{process.stderr}", file=sys.stderr)
                return False

            result = json.loads(process.stdout)
            if status_validator(result):
                return True
            else:
                sleep(self.timeout_interval)
                waited = waited + self.timeout_interval

        return False
