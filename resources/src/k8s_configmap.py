#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import Mapping, MutableSequence, Sequence

from dresources import DAction, action
from gcp_gke_cluster import GkeCluster
from k8s import K8sResource
from k8s_namespace import K8sNamespace


class K8sConfigMap(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        # TODO: dependency type validation
        self._namespace: K8sNamespace = K8sNamespace(self.get_resource_dependency('namespace'))

    @property
    def cluster(self) -> GkeCluster:
        return self.namespace.cluster

    @property
    def namespace(self) -> K8sNamespace:
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
    def data(self) -> dict:
        return self.k8s_manifest['data']

    @property
    def resource_required_resources(self) -> Mapping[str, str]:
        return {
            "namespace": "infolinks/deployster-k8s-namespace"
        }

    @property
    def k8s_manifest_schema(self) -> dict:
        schema: dict = super().k8s_manifest_schema
        schema['required'].append('data')
        schema['properties'].update({
            'data': {
                "type": "object",
                "additionalProperties": True
            }
        })
        return schema

    def infer_actions_from_actual_properties(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = super().infer_actions_from_actual_properties(actual_properties)
        if self.data != actual_properties['data']:
            actions.append(DAction(name="update-data", description=f"Update configuration map data"))
        return actions

    @action
    def update_data(self, args):
        if args: pass

        patch = json.dumps([{"op": "replace", "path": "/data", "value": self.k8s_manifest['data']}])
        subprocess.run(f"{self.kubectl_command('patch')} --type=json --patch='{patch}'",
                       check=True,
                       timeout=self.timeout,
                       shell=True)


def main():
    K8sConfigMap(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
