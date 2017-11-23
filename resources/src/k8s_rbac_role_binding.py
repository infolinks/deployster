#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import Mapping, Sequence, MutableSequence

from dresources import action, DAction
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
    def k8s_api_group(self) -> str:
        return "rbac.authorization.k8s.io"

    @property
    def k8s_api_version(self) -> str:
        return "v1"

    @property
    def k8s_kind(self) -> str:
        return "RoleBinding"

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
        schema = super().resource_config_schema
        schema['properties']['subjects'] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "apiGroup": {"type": "string"},
                    "kind": {"type": "string"},
                    "name": {"type": "string"},
                    "namespace": {"type": "string"}
                }
            }
        }
        return schema

    def infer_actions_from_actual_properties(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = super().infer_actions_from_actual_properties(actual_properties)
        # TODO: compare role-ref's namespace too
        if self.role.name != actual_properties['roleRef']['name']:
            actions.append(DAction(name="update_role_binding_role", description=f"Update role binding role"))
        if self.subjects != actual_properties['subjects']:
            actions.append(DAction(name="update-role-binding-subjects", description=f"Update role binding subjects"))
        return actions

    def build_manifest(self) -> dict:
        manifest = super().build_manifest()
        manifest['roleRef'] = {
            "apiGroup": self.role.k8s_api_group,
            "kind": self.role.k8s_kind,
            "name": self.role.name
        }
        manifest['subjects'] = self.subjects
        return manifest

    @action
    def update_role_binding_role(self, args):
        if args: pass
        patch = json.dumps({
            "roleRef": {
                "apiGroup": self.role.k8s_api_group,
                "kind": self.role.k8s_kind,
                "name": self.role.name
            }
        })

        namespace_arg = f"--namespace {self.namespace.name}"
        command = f"kubectl patch {self.k8s_kind} {self.name} {namespace_arg} --type=merge --patch '{patch}'"
        subprocess.run(command, check=True, timeout=self.timeout, shell=True)

    @action
    def update_role_binding_subjects(self, args):
        if args: pass
        patch = json.dumps({'subjects': self.subjects})
        namespace_arg = f"--namespace {self.namespace.name}"
        command = f"kubectl patch {self.k8s_kind} {self.name} {namespace_arg} --type=merge --patch '{patch}'"
        subprocess.run(command, check=True, timeout=self.timeout, shell=True)


def main():
    K8sRoleBinding(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
