#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import MutableSequence, Sequence

from dresources import DAction, collect_differences, action
from gcp_gke_cluster import GkeCluster
from k8s import K8sResource
from k8s_namespace import K8sNamespace


class K8sStorageClass(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.add_dependency(name='cluster',
                            type='infolinks/deployster-gcp-gke-cluster',
                            optional=False,
                            factory=GkeCluster)
        self.config_schema['properties']['manifest']['required'].append('spec')
        self.config_schema['properties']['manifest']['properties'].update({
            'spec': {
                "type": "object",
                "additionalProperties": True
            }
        })

    @property
    def cluster(self) -> GkeCluster:
        return self.get_dependency('cluster')

    @property
    def k8s_api_group(self) -> str:
        return "storage"

    @property
    def k8s_api_version(self) -> str:
        return "v1"

    @property
    def k8s_kind(self) -> str:
        return "StorageClass"

    @property
    def spec(self) -> dict:
        return self.k8s_manifest['spec']

    def get_actions_when_existing(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = super().get_actions_when_existing(actual_properties)
        diffs = collect_differences(self.spec, actual_properties['spec'])
        if diffs:
            actions.append(DAction(name="update-spec", description=f"Update specification"))
        return actions

    @action
    def update_spec(self, args):
        if args: pass

        patch = json.dumps([{"op": "replace", "path": "/spec", "value": self.spec}])
        subprocess.run(f"{self.kubectl_command('patch')} --type=json --patch='{patch}'",
                       check=True,
                       timeout=self.timeout,
                       shell=True)


def main():
    K8sStorageClass(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
