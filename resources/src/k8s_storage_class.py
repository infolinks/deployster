#!/usr/bin/env python3
import json
import subprocess
import sys
from typing import MutableSequence, Sequence

from dresources import DAction, action
from gcp_gke_cluster import GkeCluster
from k8s import K8sResource


class K8sStorageClass(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.add_dependency(name='cluster',
                            type='infolinks/deployster-gcp-gke-cluster',
                            optional=False,
                            factory=GkeCluster)
        self.config_schema['properties']['manifest']['required'].append('provisioner')
        self.config_schema['properties']['manifest']['properties'].update({
            'allowVolumeExpansion': {
                "type": "boolean"
            },
            'mountOptions': {
                "type": "array",
                "items": {
                    "type": "string"
                }
            },
            'parameters': {
                "type": "object",
                "additionalProperties": True
            },
            'provisioner': {
                "type": "string"
            },
            'reclaimPolicy': {
                "type": "string"
            }
        })

    @property
    def cluster(self) -> GkeCluster:
        return self.get_dependency('cluster')

    @property
    def k8s_api_group(self) -> str:
        return "storage.k8s.io"

    @property
    def k8s_api_version(self) -> str:
        return "v1"

    @property
    def k8s_kind(self) -> str:
        return "StorageClass"

    @property
    def allow_volume_expansion(self) -> bool:
        return self.k8s_manifest['allowVolumeExpansion'] if 'allowVolumeExpansion' in self.k8s_manifest else None

    @property
    def mount_options(self) -> Sequence[str]:
        return self.k8s_manifest['mountOptions'] if 'mountOptions' in self.k8s_manifest else None

    @property
    def parameters(self) -> dict:
        return self.k8s_manifest['parameters'] if 'parameters' in self.k8s_manifest else None

    @property
    def provisioner(self) -> str:
        return self.k8s_manifest['provisioner'] if 'provisioner' in self.k8s_manifest else None

    @property
    def reclaim_policy(self) -> str:
        return self.k8s_manifest['reclaimPolicy'] if 'reclaimPolicy' in self.k8s_manifest else None

    def get_actions_when_existing(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = super().get_actions_when_existing(actual_properties)

        actual_allow_volume_expansion = \
            actual_properties['allowVolumeExpansion'] if 'allowVolumeExpansion' in actual_properties else None
        actual_mount_options = actual_properties['mountOptions'] if 'mountOptions' in actual_properties else None
        actual_parameters = actual_properties['parameters'] if 'parameters' in actual_properties else None
        actual_provisioner = actual_properties['provisioner'] if 'provisioner' in actual_properties else None
        actual_reclaim_policy = actual_properties['reclaimPolicy'] if 'reclaimPolicy' in actual_properties else None

        if self.allow_volume_expansion is not None and self.allow_volume_expansion != actual_allow_volume_expansion \
                or self.mount_options is not None and self.mount_options != actual_mount_options \
                or self.parameters is not None and self.parameters != actual_parameters \
                or self.provisioner is not None and self.provisioner != actual_provisioner \
                or self.reclaim_policy is not None and self.reclaim_policy != actual_reclaim_policy:
            actions.append(DAction(name="update", description=f"Update storage class"))

        return actions

    @action
    def update(self, args):
        if args: pass

        subprocess.run(f"kubectl apply -f -",
                       input=json.dumps(self.build_creation_manifest()),
                       encoding='utf-8',
                       check=True,
                       timeout=self.timeout,
                       shell=True)

        if not self.wait_for_availability():
            raise Exception(f"{self.k8s_kind} '{self.name}' was not patched successfully.\n"
                            f"Use this command to find out more:\n"
                            f"    {self.kubectl_command('get')}")


def main():
    K8sStorageClass(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
