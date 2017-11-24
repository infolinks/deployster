#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import Mapping, Sequence, MutableSequence

from dresources import action, DAction, collect_differences
from gcp_gke_cluster import GkeCluster
from k8s import K8sResource
from k8s_namespace import K8sNamespace
from k8s_rbac_role import K8sRole


class K8sRoleBinding(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        # TODO: dependency type validation
        self._role: K8sRole = K8sRole(self.get_resource_dependency('role'))
        self._cluster = self._role.cluster

        # set subjects
        self._subjects: Sequence[dict] = self.k8s_manifest["subjects"]
        for subject in self._subjects:
            if 'kind' not in subject:
                raise Exception(f"missing 'kind' property for subject: {json.dumps(subject)}")
            elif subject['kind'] != 'ServiceAccount' and 'apiGroup' not in subject:
                subject['apiGroup'] = 'rbac.authorization.k8s.io'

        # set role, namespace & kind according to provided dependencies
        if self._role.k8s_kind == 'Role':
            self._kind = 'RoleBinding'

            # referencing a 'Role' means that we must be in the same namespace; the 'namespace' dependency not allowed
            if self.has_dependency('namespace'):
                raise Exception(
                    f"illegal config: cannot provide 'namespace' dependency when referencing non-cluster roles")

            self._namespace: K8sNamespace = self._role.namespace
            self._required_resources = {"role": "infolinks/deployster-k8s-rbac-role"}

        elif self._role.k8s_kind == 'ClusterRole':
            self._kind = 'ClusterRoleBinding'
            if self.has_dependency('namespace'):
                self._namespace: K8sNamespace = K8sNamespace(self.get_resource_dependency('namespace'))
                self._required_resources = {
                    "role": "infolinks/deployster-k8s-rbac-role",
                    "namespace": "infolinks/deployster-k8s-namespace"
                }
                if self._role.cluster.name != self._namespace.cluster.name:
                    raise Exception(f"illegal config: namespace & role dependencies must belong to the same cluster")
            else:
                self._namespace: K8sNamespace = None
                self._required_resources = {"role": "infolinks/deployster-k8s-rbac-role"}

        else:
            raise Exception(f"illegal state: role '{self._role.name}' is of unsupported kind '{self._role.k8s_kind}'")

    @property
    def cluster(self) -> GkeCluster:
        return self._cluster

    @property
    def namespace(self) -> K8sNamespace:
        return self._namespace

    @property
    def role(self) -> K8sRole:
        return self._role

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
    def subjects(self) -> Sequence[dict]:
        return self._subjects

    @property
    def resource_required_resources(self) -> Mapping[str, str]:
        return self._required_resources

    @property
    def k8s_manifest_schema(self) -> dict:
        schema: dict = super().k8s_manifest_schema
        schema['properties'].update({
            'subjects': {
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
        })
        return schema

    def infer_actions_from_actual_properties(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = super().infer_actions_from_actual_properties(actual_properties)

        actual_roleref = actual_properties['roleRef']
        if self.role.name != actual_roleref['name'] or self.role.k8s_kind != actual_roleref['kind']:
            actions.append(DAction(name="update-role-ref", description=f"Update role reference"))

        subject_diffs = collect_differences(self.subjects, actual_properties['subjects'])
        if subject_diffs:
            print(f"Found the following subject differences:\n{subject_diffs}", file=sys.stderr)
            actions.append(DAction(name="update-subjects", description=f"Update subjects"))

        return actions

    def build_creation_manifest(self) -> dict:
        manifest = super().build_creation_manifest()
        manifest['roleRef'] = {
            'apiGroup': self.role.k8s_api_group,
            'kind': self.role.k8s_kind,
            'name': self.role.name
        }
        manifest['subjects'] = self.subjects
        return manifest

    @action
    def update_role_ref(self, args):
        if args: pass

        patch = json.dumps([{
            "op": "replace",
            "path": "/roleRef",
            "value": {
                'apiGroup': self.role.k8s_api_group,
                'kind': self.role.k8s_kind,
                'name': self.role.name
            }
        }])
        subprocess.run(f"{self.kubectl_command('patch')} --type=json --patch='{patch}'",
                       check=True,
                       timeout=self.timeout,
                       shell=True)

    @action
    def update_subjects(self, args):
        if args: pass

        patch = json.dumps([{
            "op": "replace",
            "path": "/subjects",
            "value": self.subjects
        }])
        subprocess.run(f"{self.kubectl_command('patch')} --type=json --patch='{patch}'",
                       check=True,
                       timeout=self.timeout,
                       shell=True)


def main():
    K8sRoleBinding(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
