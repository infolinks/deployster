#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import Sequence, Mapping, MutableSequence

from dresources import DAction, action
from gcp_gke_cluster import GkeCluster
from k8s_rbac_cluster_role import K8sClusterRole
from k8s_resources import K8sResource


class K8sClusterRoleBinding(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self._cluster_role: K8sClusterRole = None
        self._subjects: Sequence[dict] = None
        # TODO: support creating 'role-binding' if 'namespace' is provided (ie. cluster-role constrained to a namespace)

    @property
    def cluster(self) -> GkeCluster:
        return self.cluster_role.cluster

    @property
    def cluster_role(self) -> K8sClusterRole:
        if self._cluster_role is None:
            self._cluster_role: K8sClusterRole = K8sClusterRole(self.resource_dependency('cluster-role'))
        return self._cluster_role

    @property
    def k8s_type(self) -> str:
        return "clusterrolebinding"

    @property
    def name(self) -> str:
        return self.resource_config['name']

    @property
    def subjects(self) -> Sequence[dict]:
        if self._subjects is None:
            self._subjects: Sequence[dict] = self.resource_config["subjects"]
            for subject in self._subjects:
                if 'apiGroup' not in subject:
                    subject['apiGroup'] = 'rbac.authorization.k8s.io'
        return self._subjects

    @property
    def resource_required_resources(self) -> Mapping[str, str]:
        return {
            "cluster-role": "infolinks/deployster-k8s-rbac-cluster-role"
        }

    @property
    def resource_config_schema(self) -> dict:
        return {
            "type": "object",
            "required": ["name", "subjects"],
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string"},
                "metadata": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "annotations": {"type": "object"},
                        "labels": {"type": "object"}
                    }
                },
                "subjects": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "apiGroup": {
                                "type": "string"
                            },
                            "kind": {"type": "string"},
                            "name": {"type": "string"},
                            "namespace": {"type": "string"}
                        }
                    }
                }
            }
        }

    def infer_actions_from_actual_properties(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = super().infer_actions_from_actual_properties(actual_properties)
        if self.cluster_role.name != actual_properties['roleRef']['name']:
            actions.append(DAction(name="update_cluster_role_binding_role",
                                   description=f"Update cluster-role binding role"))
        if self.subjects != actual_properties['subjects']:
            actions.append(DAction(name="update-cluster-role-binding-subjects",
                                   description=f"Update cluster-role binding subjects"))
        return actions

    @action
    def create(self, args):
        filename = f"/tmp/cluster-role-binding-{self.name}.json"
        with open(filename, 'w') as f:
            f.write(json.dumps({
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "ClusterRoleBinding",
                "metadata": {
                    "name": self.name,
                    "annotations": self.annotations,
                    "labels": self.labels
                },
                "roleRef": {
                    "apiGroup": "rbac.authorization.k8s.io",
                    "kind": "ClusterRole",
                    "name": self.cluster_role.name
                },
                "subjects": self.subjects
            }))
        command = f"kubectl create --output=json --filename={filename}"
        exit(subprocess.run(command, shell=True).returncode)

    @action
    def update_cluster_role_binding_role(self, args):
        if args: pass
        patch = json.dumps({
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "ClusterRole",
                "name": self.cluster_role.name
            }
        })
        command = f"kubectl patch {self.k8s_type} {self.name} --type=merge --patch '{patch}'"
        exit(subprocess.run(command, shell=True).returncode)

    @action
    def update_cluster_role_binding_subjects(self, args):
        if args: pass
        patch = json.dumps({
            'subjects': self.subjects
        })
        command = f"kubectl patch {self.k8s_type} {self.name} --type=merge --patch '{patch}'"
        exit(subprocess.run(command, shell=True).returncode)


def main():
    K8sClusterRoleBinding(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
