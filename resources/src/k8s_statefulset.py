#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import MutableSequence, Sequence

from dresources import DAction, collect_differences, action
from gcp_gke_cluster import GkeCluster
from k8s import K8sResource
from k8s_namespace import K8sNamespace


class K8sStatefulSet(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.add_dependency(name='namespace',
                            type='infolinks/deployster-k8s-namespace',
                            optional=False,
                            factory=K8sNamespace)
        self.config_schema['properties']['manifest']['required'].append('spec')
        self.config_schema['properties']['manifest']['properties'].update({
            'spec': {
                "type": "object",
                "additionalProperties": True
            }
        })

    @property
    def cluster(self) -> GkeCluster:
        return self.namespace.cluster

    @property
    def namespace(self) -> K8sNamespace:
        return self.get_dependency('namespace')

    @property
    def k8s_api_group(self) -> str:
        return "apps"

    @property
    def k8s_api_version(self) -> str:
        return "v1beta2"

    @property
    def k8s_kind(self) -> str:
        return "StatefulSet"

    @property
    def spec(self) -> dict:
        return self.k8s_manifest['spec']

    def get_actions_when_existing(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = super().get_actions_when_existing(actual_properties)
        diffs = collect_differences(self.spec, actual_properties['spec'])
        if diffs:
            actions.append(DAction(name="update-spec", description=f"Update specification"))
        return actions

    def check_availability(self, actual_properties: dict):
        # TODO: implement 'K8sStatefulSet.check_availability(..)'
        return True

    @action
    def update_spec(self, args):
        if args: pass

        patch = json.dumps([{"op": "replace", "path": "/spec", "value": self.spec}])
        subprocess.run(f"{self.kubectl_command('patch')} --type=json --patch='{patch}'",
                       check=True,
                       timeout=self.timeout,
                       shell=True)


def main():
    K8sStatefulSet(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
