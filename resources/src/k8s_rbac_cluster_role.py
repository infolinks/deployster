#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import Mapping, Sequence, MutableSequence

from dresources import DAction, action
from gcp_gke_cluster import GkeCluster
from k8s_resources import K8sResource


class K8sClusterRole(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self._cluster: GkeCluster = None

    @property
    def cluster(self) -> GkeCluster:
        if self._cluster is None:
            self._cluster: GkeCluster = GkeCluster(self.resource_dependency('cluster'))
        return self._cluster

    @property
    def k8s_api_group(self) -> str:
        return "rbac.authorization.k8s.io"

    @property
    def k8s_api_version(self) -> str:
        return "v1"

    @property
    def k8s_kind(self) -> str:
        return "ClusterRole"

    @property
    def name(self) -> str:
        return self.resource_config['name']

    @property
    def rules(self) -> dict:
        return self.resource_config["rules"]

    @property
    def resource_required_resources(self) -> Mapping[str, str]:
        return {
            "cluster": "infolinks/deployster-gcp-gke-cluster"
        }

    @property
    def resource_config_schema(self) -> dict:
        schema = super().resource_config_schema
        schema['properties']['rules'] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "apiGroups": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "nonResourceURLs": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "resourceNames": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "resources": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "verbs": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            }
        }
        return schema

    def infer_actions_from_actual_properties(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = super().infer_actions_from_actual_properties(actual_properties)
        if self.rules != actual_properties['rules']:
            actions.append(DAction(name="update-cluster-role-rules", description=f"Update cluster-role rules"))
        return actions

    def build_manifest(self) -> dict:
        manifest = super().build_manifest()
        manifest['rules'] = self.rules
        return manifest

    @action
    def update_cluster_role_rules(self, args):
        if args: pass
        command = f"kubectl patch {self.k8s_kind} {self.name} --type=merge --patch '{json.dumps({'rules':self.rules})}'"
        subprocess.run(command, check=True, timeout=self.timeout, shell=True)


def main():
    K8sClusterRole(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
