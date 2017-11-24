#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import Mapping, MutableSequence, Sequence

from dresources import DAction, action
from gcp_gke_cluster import GkeCluster
from k8s_namespace import K8sNamespace
from k8s_resources import K8sResource


class K8sConfigMap(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self._namespace: K8sNamespace = None

    @property
    def cluster(self) -> GkeCluster:
        return self.namespace.cluster

    @property
    def namespace(self) -> K8sNamespace:
        if self._namespace is None:
            self._namespace: K8sNamespace = K8sNamespace(self.resource_dependency('namespace'))
        return self._namespace

    @property
    def k8s_api_group(self) -> str:
        return "core"

    @property
    def k8s_api_version(self) -> str:
        return "v1"

    @property
    def k8s_kind(self) -> str:
        return "ConfigMap"

    @property
    def name(self) -> str:
        return self.resource_config['name']

    @property
    def data(self) -> dict:
        return self.resource_config['data']

    @property
    def resource_required_resources(self) -> Mapping[str, str]:
        return {
            "namespace": "infolinks/deployster-k8s-namespace"
        }

    @property
    def resource_config_schema(self) -> dict:
        schema = super().resource_config_schema
        schema['properties']['data'] = {"type": "object"}
        return schema

    def infer_actions_from_actual_properties(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = super().infer_actions_from_actual_properties(actual_properties)
        if self.data != actual_properties['data']:
            actions.append(DAction(name="update-data", description=f"Update configuration map data"))
        return actions

    def build_manifest(self) -> dict:
        manifest = super().build_manifest()
        manifest['data'] = self.data
        return manifest

    @action
    def update_data(self, args):
        if args: pass

        namespace_arg = f"--namespace {self.namespace.name}" if self.namespace is not None else ""
        patch = json.dumps({'data': self.data})
        command = f"kubectl patch {self.k8s_kind} {self.name} {namespace_arg} --type=merge --patch '{patch}'"
        subprocess.run(command, check=True, timeout=self.timeout, shell=True)


def main():
    K8sConfigMap(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
