#!/usr/bin/env python3

import json
import subprocess
import sys
from typing import Mapping, MutableSequence, Sequence

from dresources import DAction, collect_differences, action
from gcp_compute_ip_address import GcpIpAddress
from gcp_gke_cluster import GkeCluster
from k8s import K8sResource
from k8s_namespace import K8sNamespace


class K8sIngress(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self._namespace: K8sNamespace = K8sNamespace(self.get_resource_dependency('namespace'))
        self._address: GcpIpAddress = GcpIpAddress(self.get_resource_dependency('address')) \
            if self.has_dependency('address') else None

        if self._address is not None:
            if 'manifest' not in self.resource_config: self.resource_config['manifest'] = {}
            manifest = self.resource_config['manifest']

            if 'metadata' not in manifest: manifest['metadata'] = {}
            metadata = manifest['metadata']

            if 'annotations' not in metadata: metadata['annotations'] = {}
            annotations = metadata['annotations']

            annotations['kubernetes.io/ingress.global-static-ip-name'] = self._address.name

    @property
    def cluster(self) -> GkeCluster:
        return self.namespace.cluster

    @property
    def namespace(self) -> K8sNamespace:
        return self._namespace

    @property
    def k8s_api_group(self) -> str:
        return "extensions"

    @property
    def k8s_api_version(self) -> str:
        return "v1beta1"

    @property
    def k8s_kind(self) -> str:
        return "Ingress"

    @property
    def spec(self) -> dict:
        return self.k8s_manifest['spec'] if 'spec' in self.k8s_manifest else None

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
        # TODO: wait for LetsEncrypt to store the TLS?

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

        # we specifically replace selected parts inside 'spec', because LetsEncrypt will store an additional value in
        # the 'spec' - the "tls" property, which we want to leave as is.
        patch = json.dumps([
            {"op": "replace", "path": "/spec/backend", "value": spec['backend'] if 'backend' in spec else None},
            {"op": "replace", "path": "/spec/rules", "value": spec['rules'] if 'rules' in spec else None}
        ])
        subprocess.run(f"{self.kubectl_command('patch')} --type=json --patch='{patch}'",
                       check=True,
                       timeout=self.timeout,
                       shell=True)


def main():
    K8sIngress(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
