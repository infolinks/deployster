#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import Mapping, MutableSequence, Sequence

from dresources import action, DAction, collect_differences
from gcp_gke_cluster import GkeCluster
from k8s import K8sResource
from k8s_namespace import K8sNamespace


class K8sRole(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        if self.has_dependency('namespace'):
            # TODO: dependency type validation
            self._namespace: K8sNamespace = K8sNamespace(self.get_resource_dependency('namespace'))
            self._cluster: GkeCluster = self._namespace.cluster
            self._kind = 'Role'
            self._required_resources = {"namespace": "infolinks/deployster-k8s-namespace"}
        elif self.has_dependency('cluster'):
            # TODO: dependency type validation
            self._namespace = None
            self._cluster: GkeCluster = GkeCluster(self.get_resource_dependency('cluster'))
            self._kind = 'ClusterRole'
            self._required_resources = {"cluster": "infolinks/deployster-gcp-gke-cluster"}
        else:
            raise Exception(f"invalid dependencies: must have either 'cluster' or 'namespace', appropriately typed")

    @property
    def cluster(self) -> GkeCluster:
        return self._cluster

    @property
    def namespace(self) -> K8sNamespace:
        return self._namespace

    @property
    def k8s_api_group(self) -> str:
        return "rbac.authorization.k8s.io"

    @property
    def k8s_api_version(self) -> str:
        return "v1"

    @property
    def k8s_kind(self) -> str:
        return self._kind

    @property
    def rules(self) -> dict:
        return self.k8s_manifest["rules"]

    @property
    def resource_required_resources(self) -> Mapping[str, str]:
        return self._required_resources

    @property
    def k8s_manifest_schema(self) -> dict:
        schema: dict = super().k8s_manifest_schema
        schema['required'].append('rules')
        schema['properties'].update({
            'rules': {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "apiGroups": {"type": "array", "items": {"type": "string"}},
                        "nonResourceURLs": {"type": "array", "items": {"type": "string"}},
                        "resourceNames": {"type": "array", "items": {"type": "string"}},
                        "resources": {"type": "array", "items": {"type": "string"}},
                        "verbs": {"type": "array", "items": {"type": "string"}}
                    }
                }
            }
        })
        return schema

    def infer_actions_from_actual_properties(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = super().infer_actions_from_actual_properties(actual_properties)
        diffs = collect_differences(self.rules, actual_properties['rules'])
        if diffs:
            print(f"Found the following differences:\n{diffs}", file=sys.stderr)
            actions.append(DAction(name="update-rules", description=f"Update rules"))
        return actions

    @action
    def update_role_rules(self, args):
        if args: pass

        patch = json.dumps([{"op": "replace", "path": "/rules", "value": self.rules}])
        subprocess.run(f"{self.kubectl_command('patch')} --type=json --patch='{patch}'",
                       check=True,
                       timeout=self.timeout,
                       shell=True)


def main():
    K8sRole(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
