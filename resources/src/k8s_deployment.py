#!/usr/bin/env python3

import json
import sys
from typing import Mapping

from gcp_gke_cluster import GkeCluster
from k8s_namespace import K8sNamespace
from k8s_spec_resource import K8sSpecificationResource


class K8sDeployment(K8sSpecificationResource):

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
        return "apps"

    @property
    def k8s_api_version(self) -> str:
        return "v1beta2"

    @property
    def k8s_kind(self) -> str:
        return "Deployment"

    @property
    def name(self) -> str:
        return self.resource_config['name']

    @property
    def spec(self) -> str:
        return self.resource_config['spec']

    @property
    def resource_required_resources(self) -> Mapping[str, str]:
        return {
            "namespace": "infolinks/deployster-k8s-namespace"
        }

    def validate_status(self, result: dict) -> bool:
        if 'status' not in result:
            return False

        deployment_status = result['status']
        if 'unavailableReplicas' not in deployment_status:
            return True

        unavailable_replicas = deployment_status['unavailableReplicas']
        if unavailable_replicas == 0:
            return True

        print(f"waiting... ({unavailable_replicas} unavailable replicas)", file=sys.stderr)
        return False


def main():
    K8sDeployment(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
