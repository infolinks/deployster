#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import Mapping, Sequence

from dresources import action
from gcp_gke_cluster import GkeCluster
from k8s_namespace import K8sNamespace
from k8s_rbac_role import K8sRole
from k8s_resources import K8sResource


class K8sRoleBinding(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self._role: K8sRole = None
        self._subjects: Sequence[dict] = None

    @property
    def cluster(self) -> GkeCluster:
        return self.namespace.cluster

    @property
    def namespace(self) -> K8sNamespace:
        return self.role.namespace

    @property
    def role(self) -> K8sRole:
        if self._role is None:
            self._role: K8sRole = K8sRole(self.resource_dependency('role'))
        return self._role

    @property
    def k8s_type(self) -> str:
        return "rolebinding"

    @property
    def name(self) -> str:
        return self.resource_config['name']

    @property
    def subjects(self) -> Sequence[dict]:
        if self._subjects is None:
            self._subjects: Sequence[dict] = self.resource_config["subjects"]
        return self._subjects

    @property
    def resource_required_resources(self) -> Mapping[str, str]:
        return {
            "role": "infolinks/deployster-k8s-rbac-role"
        }

    @property
    def resource_config_schema(self) -> dict:
        return {
            "type": "object",
            "required": ["name"],
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

    def discover_actual_properties(self):
        command = f"kubectl get {self.k8s_type} {self.name} --namespace {self.namespace.name} " \
                  f"                                        --ignore-not-found=true " \
                  f"                                        --output=json"
        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode != 0:
            raise Exception(f"illegal state: failed getting '{self.k8s_type}' '{self.name}':\n" f"{process.stderr}")
        else:
            return json.loads(process.stdout) if process.stdout else None

    @action
    def create(self, args):
        filename = f"/tmp/role-binding-{self.name}.json"
        with open(filename, 'w') as f:
            f.write(json.dumps({
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "RoleBinding",
                "metadata": {
                    "name": self.name,
                    "namespace": self.namespace.name,
                    "annotations": self.annotations,
                    "labels": self.labels
                },
                "roleRef": {
                    "apiGroup": "rbac.authorization.k8s.io",
                    "kind": "Role",
                    "name": self.role.name
                },
                "subjects": self.subjects
            }))
        command = f"kubectl create --output=json --filename={filename}"
        exit(subprocess.run(command, shell=True).returncode)

    @action
    def update_role_binding_role(self, args):
        if args: pass
        patch = json.dumps({
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "Role",
                "name": self.role.name
            }
        })
        command = f"kubectl patch {self.k8s_type} {self.name} --type=merge --patch '{patch}'"
        exit(subprocess.run(command, shell=True).returncode)

    @action
    def update_role_binding_subjects(self, args):
        if args: pass
        patch = json.dumps({
            'subjects': self.subjects
        })
        command = f"kubectl patch {self.k8s_type} {self.name} --type=merge --patch '{patch}'"
        exit(subprocess.run(command, shell=True).returncode)


def main():
    K8sRoleBinding(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
