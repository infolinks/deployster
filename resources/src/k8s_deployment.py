#!/usr/bin/env python3

import json
import subprocess
import sys
from time import sleep
from typing import Mapping, Sequence, MutableSequence

from dresources import action, DAction, collect_differences
from gcp_gke_cluster import GkeCluster
from k8s_namespace import K8sNamespace
from k8s_resources import K8sResource


class K8sDeployment(K8sResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self._namespace: K8sNamespace = None
        self._timeout: int = self.resource_config['timeout'] if 'timeout' in self.resource_config else 60

    @property
    def cluster(self) -> GkeCluster:
        return self.namespace.cluster

    @property
    def namespace(self) -> K8sNamespace:
        if self._namespace is None:
            self._namespace: K8sNamespace = K8sNamespace(self.resource_dependency('namespace'))
        return self._namespace

    @property
    def k8s_type(self) -> str:
        return "deployment"

    @property
    def name(self) -> str:
        return self.resource_config['name']

    @property
    def timeout(self) -> int:
        return self._timeout

    @property
    def spec(self) -> str:
        return self.resource_config['spec']

    @property
    def resource_required_resources(self) -> Mapping[str, str]:
        return {
            "namespace": "infolinks/deployster-k8s-namespace"
        }

    @property
    def resource_config_schema(self) -> dict:
        return {
            "type": "object",
            "required": ["name", "spec"],
            "additionalProperties": False,
            "properties": {
                "name": {
                    "type": "string"
                },
                "timeout": {
                    "description": "How many seconds to wait until deployment is ready",
                    "type": "integer"
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
                },
                "spec": {
                    "type": "object",
                    "additionalProperties": True
                }
            }
        }

    def discover_actual_properties(self):
        command = f"kubectl get {self.k8s_type} {self.name} --namespace {self.namespace.name} " \
                  f"                                        --ignore-not-found=true " \
                  f"                                        --output=json"
        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode != 0:
            raise Exception(f"illegal state: failed getting '{self.k8s_type}' '{self.name}':\n" f"{process.stderr}")
        else:
            return json.loads(process.stdout) if process.stdout else None

    def infer_actions_from_actual_properties(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = super().infer_actions_from_actual_properties(actual_properties)

        diffs = collect_differences(desired=self.spec, actual=actual_properties["spec"], path=["spec"])
        if diffs:
            actions.append(DAction(name='update-spec', description=f"Update specification"))

        return actions

    def wait_for_resource(self) -> bool:
        waited = 0
        interval = 5
        while waited < self.timeout:
            command = f"kubectl get deployment {self.name} --namespace {self.namespace.name} --output=json"
            process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if process.returncode != 0:
                print(f"failed polling for deployment status:\n{process.stderr}", file=sys.stderr)
                return False

            result = json.loads(process.stdout)
            deployment_status = result['status']
            unavailable_replicas = \
                deployment_status['unavailableReplicas'] if 'unavailableReplicas' in deployment_status else 0
            if unavailable_replicas == 0:
                return True
            else:
                print(f"waiting... ({unavailable_replicas} unavailable replicas)", file=sys.stderr)
                sleep(interval)
                waited = waited + interval

        print(f"deployment '{self.name}' is still not available (waited for {self.timeout} seconds)", file=sys.stderr)
        print(f"use this command to find out more:", file=sys.stderr)
        print(f"    kubectl get deployment {self.name} --namespace {self.namespace.name} --output=yaml",
              file=sys.stderr)
        return False

    @action
    def create(self, args):
        filename = f"/tmp/role-{self.name}.json"
        with open(filename, 'w') as f:
            f.write(json.dumps({
                "apiVersion": "apps/v1beta1",
                "kind": "Deployment",
                "metadata": {
                    "name": self.name,
                    "namespace": self.namespace.name,
                    "annotations": self.annotations,
                    "labels": self.labels
                },
                "spec": self.spec
            }))

        command = f"kubectl create --output=json --filename={filename}"
        process = subprocess.run(command, shell=True)
        if process.returncode != 0 or not self.wait_for_resource():
            exit(1)

    @action
    def update_spec(self, args):
        if args: pass
        command = f"kubectl patch {self.k8s_type} {self.name} --namespace {self.namespace.name} " \
                  f"                                          --type=merge " \
                  f"                                          --patch '{json.dumps({'spec':self.spec})}'"
        process = subprocess.run(command, shell=True)
        if process.returncode != 0 or not self.wait_for_resource():
            exit(1)


def main():
    K8sDeployment(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
