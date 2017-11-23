#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import Mapping, MutableSequence, Sequence

from dresources import action, DAction
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
    def k8s_api_group(self) -> str:
        return "rbac.authorization.k8s.io"

    @property
    def k8s_api_version(self) -> str:
        return "v1"

    @property
    def k8s_kind(self) -> str:
        return "Role"

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
            actions.append(DAction(name="update-role-rules", description=f"Update role rules"))
        return actions

    def build_manifest(self) -> dict:
        manifest = super().build_manifest()
        manifest['rules'] = self.rules
        return manifest

    @action
    def update_role_rules(self, args):
        if args: pass

        namespace_arg = f"--namespace {self.namespace.name}" if self.namespace is not None else ""
        patch = json.dumps({'rules': self.rules})
        command = f"kubectl patch {self.k8s_kind} {self.name} {namespace_arg} --type=merge --patch '{patch}'"
        subprocess.run(command, check=True, timeout=self.timeout, shell=True)


def main():
    K8sRole(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
