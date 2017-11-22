#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import Mapping

from gcp_gke_cluster import GkeCluster
from k8s_resources import K8sResource


class K8sNamespace(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self._cluster: GkeCluster = None

    @property
    def cluster(self) -> GkeCluster:
        if self._cluster is None:
            self._cluster: GkeCluster = GkeCluster(self.resource_dependency('cluster'))
        return self._cluster

    @property
    def k8s_type(self) -> str:
        return "namespace"

    @property
    def name(self) -> str:
        return self.resource_config['name']

    @property
    def resource_required_resources(self) -> Mapping[str, str]:
        return {
            "cluster": "infolinks/deployster-gcp-gke-cluster"
        }

    @property
    def resource_config_schema(self) -> dict:
        return {
            "type": "object",
            "required": ["name"],
            "additionalProperties": False,
            "properties": {
                "name": {
                    "type": "string"
                },
                "metadata": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "annotations": {
                            "type": "object"
                        },
                        "labels": {
                            "type": "object"
                        }
                    }
                }
            }
        }

    def create(self):
        command = f"kubectl create {self.k8s_type} {self.name} --output=json"
        exit(subprocess.run(command, shell=True).returncode)


def main():
    K8sNamespace(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
