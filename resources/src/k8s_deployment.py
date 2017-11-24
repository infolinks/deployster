#!/usr/bin/env python3

import json
import sys
from typing import Mapping, MutableSequence, Sequence

from dresources import DAction, collect_differences
from gcp_gke_cluster import GkeCluster
from k8s import K8sResource
from k8s_namespace import K8sNamespace


class K8sDeployment(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        # TODO: dependency type validation
        self._namespace: K8sNamespace = K8sNamespace(self.get_resource_dependency('namespace'))

    @property
    def cluster(self) -> GkeCluster:
        return self.namespace.cluster

    @property
    def namespace(self) -> K8sNamespace:
        return self._namespace

    @property
    def k8s_api_group(self) -> str:
        return "apps"

    @property
    def k8s_api_version(self) -> str:
        return "v1beta2"

    @property
    def k8s_kind(self) -> str:
        return "Deployment"

    @property
    def resource_required_resources(self) -> Mapping[str, str]:
        return {
            "namespace": "infolinks/deployster-k8s-namespace"
        }

    @property
    def k8s_manifest_schema(self) -> dict:
        schema: dict = super().k8s_manifest_schema
        schema['required'].append('spec')
        schema['properties'].update({
            'spec': {
                "type": "object",
                "additionalProperties": True
            }
        })
        return schema

    def infer_actions_from_actual_properties(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = super().infer_actions_from_actual_properties(actual_properties)
        diffs = collect_differences(self.k8s_manifest['spec'], actual_properties['spec'])
        if diffs:
            print(f"Found the following differences:\n{diffs}", file=sys.stderr)
            actions.append(DAction(name="update-spec", description=f"Update specification"))
        return actions

    def is_available(self, actual_properties: dict):
        if 'status' not in actual_properties:
            return False

        deployment_status = actual_properties['status']
        if 'unavailableReplicas' not in deployment_status:
            return True

        unavailable_replicas = deployment_status['unavailableReplicas']
        if unavailable_replicas == 0:
            return True

        return False


def main():
    K8sDeployment(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
