#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import MutableSequence, Sequence, Mapping

from dresources import DAction, action
from gcp_gke_cluster import GkeCluster
from k8s import K8sResource
from k8s_namespace import K8sNamespace


class K8sConfigMap(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.add_dependency(name='namespace',
                            type='infolinks/deployster-k8s-namespace',
                            optional=False,
                            factory=K8sNamespace)
        self.config_schema['properties']['manifest']['required'].append('data')
        self.config_schema['properties']['manifest']['properties'].update({
            "data": {
                "type": "object",
                "additionalProperties": False,
                "patternProperties": {
                    ".+": {"type": "string"}
                }
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
        return "core"

    @property
    def k8s_api_version(self) -> str:
        return "v1"

    @property
    def k8s_kind(self) -> str:
        return "ConfigMap"

    @property
    def data(self) -> Mapping[str, str]:
        return self.k8s_manifest['data']

    def get_actions_when_existing(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = super().get_actions_when_existing(actual_properties)
        if self.data != actual_properties['data']:
            actions.append(DAction(name="update-data", description=f"Update data"))
        return actions

    @action
    def update_data(self, args):
        if args: pass

        patch = json.dumps([{"op": "replace", "path": "/data", "value": self.data}])
        subprocess.run(f"{self.kubectl_command('patch')} --type=json --patch='{patch}'",
                       check=True,
                       timeout=self.timeout,
                       shell=True)


def main():
    K8sConfigMap(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
