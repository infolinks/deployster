#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import MutableSequence, Sequence

from dresources import action, DAction, collect_differences
from gcp_gke_cluster import GkeCluster
from k8s import K8sResource
from k8s_namespace import K8sNamespace


class K8sRbacRole(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.add_dependency(name='namespace',
                            type='infolinks/deployster-k8s-namespace',
                            optional=True,
                            factory=K8sNamespace)
        self.add_dependency(name='cluster',
                            type='infolinks/deployster-gcp-gke-cluster',
                            optional=True,
                            factory=GkeCluster)
        self.config_schema['properties']['manifest']['required'].append('rules')
        self.config_schema['properties']['manifest']['properties'].update({
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

    @property
    def cluster(self) -> GkeCluster:
        cluster: GkeCluster = self.get_dependency('cluster')
        namespace: K8sNamespace = self.get_dependency('namespace')

        if cluster and namespace:
            raise Exception(f"illegal config: must specify either 'cluster' or 'namespace' dependencies (not both)")

        elif cluster and not namespace:
            # this is a cluster role
            return cluster

        elif not cluster and namespace:
            # this is a namespace role
            return namespace.cluster

        else:
            raise Exception(f"illegal config: must specify one of 'cluster' or 'namespace' dependencies")

    @property
    def namespace(self) -> K8sNamespace:
        cluster: GkeCluster = self.get_dependency('cluster')
        namespace: K8sNamespace = self.get_dependency('namespace')

        if cluster and namespace:
            raise Exception(f"illegal config: must specify either 'cluster' or 'namespace' dependencies (not both)")

        elif cluster and not namespace:
            # this is a cluster role
            # noinspection PyTypeChecker
            return None

        elif not cluster and namespace:
            # this is a namespace role
            return namespace

        else:
            raise Exception(f"illegal config: must specify one of 'cluster' or 'namespace' dependencies")

    @property
    def k8s_api_group(self) -> str:
        return "rbac.authorization.k8s.io"

    @property
    def k8s_api_version(self) -> str:
        return "v1"

    @property
    def k8s_kind(self) -> str:
        cluster: GkeCluster = self.get_dependency('cluster')
        namespace: K8sNamespace = self.get_dependency('namespace')

        if cluster and namespace:
            raise Exception(f"illegal config: must specify either 'cluster' or 'namespace' dependencies (not both)")

        elif cluster and not namespace:
            # this is a cluster role
            return 'ClusterRole'

        elif not cluster and namespace:
            # this is a namespace role
            return 'Role'

        else:
            raise Exception(f"illegal config: must specify one of 'cluster' or 'namespace' dependencies")

    @property
    def rules(self) -> dict:
        return self.k8s_manifest["rules"]

    def get_actions_when_existing(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = super().get_actions_when_existing(actual_properties)
        if collect_differences(self.rules, actual_properties['rules']):
            actions.append(DAction(name="update-rules", description=f"Update rules"))
        return actions

    @action
    def update_rules(self, args):
        if args: pass

        patch = json.dumps([{"op": "replace", "path": "/rules", "value": self.rules}])
        subprocess.run(f"{self.kubectl_command('patch')} --type=json --patch='{patch}'",
                       check=True,
                       timeout=self.timeout,
                       shell=True)


def main():
    K8sRbacRole(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
