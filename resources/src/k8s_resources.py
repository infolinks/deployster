import argparse
import json
import subprocess
from abc import abstractmethod
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

    @property
    @abstractmethod
    def cluster(self) -> GkeCluster:
        raise Exception(f"illegal state: 'cluster' property not implemented")

    @property
    @abstractmethod
    def k8s_type(self) -> str:
        raise Exception(f"illegal state: 'k8s_type' property not implemented")

    @property
    @abstractmethod
    def name(self) -> str:
        raise Exception(f"illegal state: 'name' property not implemented")

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

    def discover_actual_properties(self):
        command = f"kubectl get {self.k8s_type} {self.name} --ignore-not-found=true --output=json"
        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode != 0:
            raise Exception(f"illegal state: failed getting '{self.k8s_type}' '{self.name}':\n" f"{process.stderr}")
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
                # TODO: create 'update_annotation' action
                actions.append(DAction(name='update-annotation',
                                       description=f"Update annotation '{ann_name}'",
                                       args=[ann_name, ann_value]))

        # compare labels
        actual_labels = actual_metadata['labels'] if 'labels' in actual_metadata else {}
        for label_name, label_value in self.labels.items():
            if label_name not in actual_labels or label_value != actual_labels[label_name]:
                # TODO: create 'update_label' action
                actions.append(DAction(name='update-label',
                                       description=f"Update label '{ann_name}'",
                                       args=[label_name, label_value]))

        # if any actions inferred, we're STALE; otherwise we're VALID
        return actions

    @property
    def actions_for_missing_status(self) -> Sequence[DAction]:
        return [DAction(name='create', description=f"Create {self.k8s_type} '{self.name}'")]

    def define_action_args(self, action: str, argparser: argparse.ArgumentParser):
        super().define_action_args(action, argparser)
        if action == 'update_annotation':
            argparser.add_argument('name', metavar='NAME', help="name of the annotation to set")
            argparser.add_argument('value', metavar='VALUE', help="value for the annotation")
        elif action == 'update_label':
            argparser.add_argument('name', metavar='NAME', help="name of the label to set")
            argparser.add_argument('value', metavar='VALUE', help="value for the label")

    @action
    def create(self, args):
        raise Exception(f"illegal state: 'create' not implemented")

    @action
    def update_annotation(self, args):
        command = f"kubectl annotate {self.k8s_type} {self.name} {args.name}='{args.value}' --overwrite"
        exit(subprocess.run(command, shell=True).returncode)

    @action
    def update_label(self, args):
        command = f"kubectl label {self.k8s_type} {self.name} {args.name}='{args.value}' --overwrite"
        exit(subprocess.run(command, shell=True).returncode)

    def execute_action(self, action_name: str, action_method: Callable[..., Any], args: argparse.Namespace):
        if action_name != 'init':
            self.cluster.authenticate()
        super().execute_action(action_name, action_method, args)
