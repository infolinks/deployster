#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import MutableSequence, Sequence

from dresources import DAction, collect_differences, action
from gcp_compute_ip_address import GcpIpAddress
from gcp_gke_cluster import GkeCluster
from k8s import K8sResource
from k8s_namespace import K8sNamespace


class K8sService(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.add_dependency(name='namespace',
                            type='infolinks/deployster-k8s-namespace',
                            optional=False,
                            factory=K8sNamespace)
        self.add_dependency(name='address',
                            type='infolinks/deployster-gcp-compute-ip-address',
                            optional=True,
                            factory=GcpIpAddress)
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
    def address(self) -> GcpIpAddress:
        return self.get_dependency('address')

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
        return self.k8s_manifest['spec']

    @property
    def service_type(self) -> str:
        return self.spec['type'] if self.spec and 'type' in self.spec else "ClusterIP"

    @action
    def init(self, args) -> None:
        if 'loadBalancerIP' in self.spec:
            raise Exception(f"illegal config: the 'loadBalancerIP' is not allowed; add 'address' dependency instead "
                            f"(and only for services of type 'LoadBalancer').")
        super().init(args)

    @action
    def state(self, args) -> None:
        if self.service_type == 'LoadBalancer' and self.address is None:
            raise Exception(f"illegal config: the 'address' dependency is required when service type is 'LoadBalancer'")
        elif self.service_type != 'LoadBalancer' and self.address is not None:
            raise Exception(
                f"illegal config: the 'address' dependency is only allowed when service type is 'LoadBalancer'")
        super().state(args)

    def get_actions_when_existing(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = super().get_actions_when_existing(actual_properties)
        if collect_differences(self.spec, actual_properties['spec']):
            actions.append(DAction(name="update-spec", description=f"Update specification"))
        elif self.service_type == 'LoadBalancer':
            if self.address.ip_address != actual_properties['spec']['loadBalancerIP']:
                actions.append(DAction(name="update-spec", description=f"Update specification"))
        return actions

    def build_creation_manifest(self) -> dict:
        manifest = super().build_creation_manifest()
        if self.service_type == 'LoadBalancer':
            manifest['spec']['loadBalancerIP'] = self.address.ip_address
        return manifest

    def check_availability(self, actual_properties: dict):
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

        spec = {}
        spec.update(self.spec)
        if self.service_type == 'LoadBalancer':
            spec['loadBalancerIP'] = self.address.ip_address

        patch = json.dumps([{"op": "replace", "path": "/spec", "value": spec}])
        subprocess.run(f"{self.kubectl_command('patch')} --type=json --patch='{patch}'",
                       check=True,
                       timeout=self.timeout,
                       shell=True)


def main():
    K8sService(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
