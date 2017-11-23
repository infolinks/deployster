#!/usr/bin/env python3

import json
import sys
from typing import Mapping

from gcp_gke_cluster import GkeCluster
from k8s_namespace import K8sNamespace
from k8s_resources import K8sResource


class K8sServiceAccount(K8sResource):

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
        return "ServiceAccount"

    @property
    def name(self) -> str:
        return self.resource_config['name']

    @property
    def resource_required_resources(self) -> Mapping[str, str]:
        return {
            "namespace": "infolinks/deployster-k8s-namespace"
        }


def main():
    K8sServiceAccount(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
