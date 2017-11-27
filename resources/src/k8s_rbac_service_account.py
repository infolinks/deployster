#!/usr/bin/env python3

import json
import sys

from gcp_gke_cluster import GkeCluster
from k8s import K8sResource
from k8s_namespace import K8sNamespace


class K8sRbacServiceAccount(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.add_dependency(name='namespace',
                            type='infolinks/deployster-k8s-namespace',
                            optional=False,
                            factory=K8sNamespace)

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
        return "ServiceAccount"


def main():
    K8sRbacServiceAccount(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
