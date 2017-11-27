#!/usr/bin/env python3

import json
import sys

from gcp_gke_cluster import GkeCluster
from k8s import K8sResource


class K8sNamespace(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.add_dependency(name='cluster',
                            type='infolinks/deployster-gcp-gke-cluster',
                            optional=False,
                            factory=GkeCluster)

    @property
    def cluster(self) -> GkeCluster:
        return self.get_dependency('cluster')

    @property
    def k8s_api_group(self) -> str:
        return "core"

    @property
    def k8s_api_version(self) -> str:
        return "v1"

    @property
    def k8s_kind(self) -> str:
        return "Namespace"


def main():
    K8sNamespace(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
