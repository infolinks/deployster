#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import Mapping, MutableSequence, Sequence

from dresources import DAction, collect_differences, action
from gcp_gke_cluster import GkeCluster
from k8s import K8sResource
from k8s_namespace import K8sNamespace


class K8sService(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self._namespace: K8sNamespace = K8sNamespace(self.get_resource_dependency('namespace'))

    @property
    def cluster(self) -> GkeCluster:
        return self.namespace.cluster

    @property
    def namespace(self) -> K8sNamespace:
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
    def spec(self) -> dict:
        return self.k8s_manifest['spec'] if 'spec' in self.k8s_manifest else None

    @property
    def service_type(self) -> str:
        return self.spec['type'] if self.spec and 'type' in self.spec else "ClusterIP"

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
        diffs = collect_differences(self.spec, actual_properties['spec'])
        if diffs:
            print(f"Found the following differences:\n{diffs}", file=sys.stderr)
            actions.append(DAction(name="update-spec", description=f"Update specification"))
        return actions

    def is_available(self, actual_properties: dict):
        if self.service_type != 'LoadBalancer':
            return True

        if 'status' not in actual_properties:
            return False

        status = actual_properties['status']
        if 'loadBalancer' not in status:
            return False

        load_balancer_status = status['loadBalancer']
        if 'ingress' not in load_balancer_status:
            return False

        ingresses_status = load_balancer_status['ingress']
        if [ing for ing in ingresses_status if 'hostname' in ing or 'ip' in ing]:
            return True
        else:
            return False

    @action
    def update_spec(self, args):
        if args: pass

        patch = json.dumps([{"op": "replace", "path": "/spec", "value": self.spec}])
        subprocess.run(f"{self.kubectl_command('patch')} --type=json --patch='{patch}'",
                       check=True,
                       timeout=self.timeout,
                       shell=True)


def main():
    K8sService(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
