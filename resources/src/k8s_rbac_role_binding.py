#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import Mapping, Sequence, MutableSequence

from dresources import action, DAction, collect_differences
from gcp_gke_cluster import GkeCluster
from k8s import K8sResource
from k8s_namespace import K8sNamespace
from k8s_rbac_group import K8sRbacGroup
from k8s_rbac_role import K8sRbacRole
from k8s_rbac_service_account import K8sRbacServiceAccount
from k8s_rbac_user import K8sRbacUser


class K8sRoleBinding(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.add_dependency(name='namespace',
                            type='infolinks/deployster-k8s-namespace',
                            optional=True,
                            factory=K8sNamespace)
        self.add_dependency(name='role',
                            type='infolinks/deployster-k8s-rbac-role',
                            optional=False,
                            factory=K8sRbacRole)
        self.add_dependency(name='user',
                            type='infolinks/deployster-k8s-rbac-user',
                            optional=True,
                            factory=K8sRbacUser)
        self.add_dependency(name='group',
                            type='infolinks/deployster-k8s-rbac-group',
                            optional=True,
                            factory=K8sRbacGroup)
        self.add_dependency(name='service-account',
                            type='infolinks/deployster-k8s-rbac-service-account',
                            optional=True,
                            factory=K8sRbacServiceAccount)

    @property
    def cluster(self) -> GkeCluster:
        return self.role.cluster

    @property
    def namespace(self) -> K8sNamespace:
        role: K8sRbacRole = self.get_dependency('role')
        namespace: K8sNamespace = self.get_dependency('namespace')
        if role.k8s_kind == 'Role':
            if namespace:
                # fail because the namespace MUST be derived from the role when role is a namespaced role
                raise Exception(f"illegal config: namespace must be derived from role, because it is a namespaced "
                                f"role. remove the 'namespace' dependency.")
            else:
                return role.namespace
        elif role.k8s_kind == 'ClusterRole':
            return namespace
        else:
            raise Exception(f"illegal state: unknown role type '{role.k8s_kind}'")

    @property
    def role(self) -> K8sRbacRole:
        return self.get_dependency('role')

    @property
    def subject(self) -> Mapping[str, str]:
        user: K8sRbacUser = self.get_dependency('user')
        group: K8sRbacGroup = self.get_dependency('group')
        svc_acc: K8sRbacServiceAccount = self.get_dependency('service-account')
        subjects = [dep for dep in [user, group, svc_acc] if dep is not None]
        if len(subjects) > 1:
            raise Exception(
                f"illegal config: only one of 'user', 'group' or 'service-account' dependencies may be provided")
        elif user:
            return {'kind': user.k8s_kind, 'name': user.name}
        elif group:
            return {'kind': group.k8s_kind, 'name': group.name}
        elif svc_acc:
            return {'kind': svc_acc.k8s_kind, 'name': svc_acc.name, 'namespace': svc_acc.namespace.name}
        else:
            raise Exception(
                f"illegal config: one of 'user', 'group' or 'service-account' dependencies must be provided")

    @property
    def k8s_api_group(self) -> str:
        return "rbac.authorization.k8s.io"

    @property
    def k8s_api_version(self) -> str:
        return "v1"

    @property
    def k8s_kind(self) -> str:
        role: K8sRbacRole = self.get_dependency('role')
        namespace: K8sNamespace = self.get_dependency('namespace')
        if role.k8s_kind == 'Role':
            if namespace:
                # fail because the namespace MUST be derived from the role when role is a namespaced role
                raise Exception(f"illegal config: namespace must be derived from role, because it is a namespaced "
                                f"role. remove the 'namespace' dependency.")
            else:
                return 'RoleBinding'
        elif role.k8s_kind == 'ClusterRole':
            if namespace:
                return 'RoleBinding'
            else:
                return 'ClusterRoleBinding'
        else:
            raise Exception(f"illegal state: unknown role type '{role.k8s_kind}'")

    def get_actions_when_missing(self) -> Sequence[DAction]:
        # call 'self.subject' just so it validates that a subject was provided (instead of failon creation)
        # noinspection PyUnusedLocal
        subject = self.subject
        return super().get_actions_when_missing()

    def get_actions_when_existing(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = super().get_actions_when_existing(actual_properties)

        actual_roleref = actual_properties['roleRef']
        if self.role.name != actual_roleref['name'] or self.role.k8s_kind != actual_roleref['kind']:
            actions.append(DAction(name="update-role-ref", description=f"Update role reference"))

        if collect_differences([self.subject], actual_properties['subjects']):
            actions.append(DAction(name="update-subjects", description=f"Update subjects"))

        return actions

    def build_creation_manifest(self) -> dict:
        manifest = super().build_creation_manifest()
        manifest['roleRef'] = {
            'apiGroup': self.role.k8s_api_group,
            'kind': self.role.k8s_kind,
            'name': self.role.name
        }
        manifest['subjects'] = [self.subject]
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
            "value": [self.subject]
        }])
        subprocess.run(f"{self.kubectl_command('patch')} --type=json --patch='{patch}'",
                       check=True,
                       timeout=self.timeout,
                       shell=True)


def main():
    K8sRoleBinding(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
