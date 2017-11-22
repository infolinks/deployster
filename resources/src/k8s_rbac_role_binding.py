#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import Mapping

from gcp_gke_cluster import GkeCluster
from k8s_namespace import K8sNamespace
from k8s_rbac_role import K8sRole
from k8s_resources import K8sResource


class K8sRoleBinding(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self._namespace: K8sNamespace = None
        self._role: K8sRole = None

    @property
    def cluster(self) -> GkeCluster:
        return self.namespace.cluster

    @property
    def namespace(self) -> K8sNamespace:
        if self._namespace is None:
            self._namespace: K8sNamespace = K8sNamespace(self.resource_dependency('namespace'))
        return self._namespace

    @property
    def role(self) -> K8sRole:
        if self._role is None:
            # TODO: validate that 'namespace' and 'role' and in the same cluster
            self._role: K8sRole = K8sRole(self.resource_dependency('role'))
        return self._role

    @property
    def k8s_type(self) -> str:
        return "role"

    @property
    def name(self) -> str:
        return self.resource_config['name']

    @property
    def rules(self) -> dict:
        return self.resource_config["rules"]

    @property
    def resource_required_resources(self) -> Mapping[str, str]:
        return {
            "namespace": "infolinks/deployster-k8s-namespace",
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
                "rules": {
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
            }
        }

    def create(self):
        command = f"kubectl create {self.k8s_type} {self.name} --namespace {self.namespace.name} --output=json"
        exit(subprocess.run(command, shell=True).returncode)


def main():
    K8sRoleBinding(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
