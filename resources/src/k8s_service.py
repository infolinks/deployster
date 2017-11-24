#!/usr/bin/env python3

import json
import sys
from typing import Mapping

from gcp_gke_cluster import GkeCluster
from k8s_namespace import K8sNamespace
from k8s_spec_resource import K8sSpecificationResource


class K8sService(K8sSpecificationResource):

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
        return "core"

    @property
    def k8s_api_version(self) -> str:
        return "v1"

    @property
    def k8s_kind(self) -> str:
        return "Service"

    @property
    def name(self) -> str:
        return self.resource_config['name']

    @property
    def spec(self) -> dict:
        return self.resource_config['spec']

    @property
    def resource_required_resources(self) -> Mapping[str, str]:
        return {
            "namespace": "infolinks/deployster-k8s-namespace"
        }

    def validate_status(self, result: dict) -> bool:
        if 'spec' not in result:
            return False

        spec = result['spec']
        if 'type' not in spec:
            return True

        type = spec['type']
        if type != 'LoadBalancer':
            return True

        if 'status' not in result:
            return False

        status = result['status']
        if 'loadBalancer' not in status:
            return False

        load_balancer_status = status['loadBalancer']
        if 'ingress' not in load_balancer_status:
            return False

        ingresses_status = load_balancer_status['ingress']
        if [ing for ing in ingresses_status if 'hostname' in ing or 'ip' in ing]:
            return True

        return False


def main():
    K8sService(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
