#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import Mapping

from dresources import action
from gcp_gke_cluster import GkeCluster
from k8s_namespace import K8sNamespace
from k8s_resources import K8sResource


class K8sRole(K8sResource):

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
            "namespace": "infolinks/deployster-k8s-namespace"
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
        filename = f"/tmp/role-{self.name}.json"
        with open(filename, 'w') as f:
            f.write(json.dumps({
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "Role",
                "metadata": {
                    "name": self.name,
                    "namespace": self.namespace.name,
                    "annotations": self.annotations,
                    "labels": self.labels
                },
                "rules": self.rules
            }))
        command = f"kubectl create --output=json --filename={filename}"
        exit(subprocess.run(command, shell=True).returncode)

    @action
    def update_role_rules(self, args):
        if args: pass
        command = f"kubectl patch {self.k8s_type} {self.name} --type=merge --patch '{json.dumps({'rules':self.rules})}'"
        exit(subprocess.run(command, shell=True).returncode)


def main():
    K8sRole(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
