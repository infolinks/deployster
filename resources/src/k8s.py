import sys
import time
from copy import deepcopy
from pprint import pprint
from time import sleep
from typing import Sequence, MutableSequence

from dresources import DAction, action, DResource
from dresources_util import collect_differences
from external_services import ExternalServices


class K8sResource(DResource):

    def __init__(self, data: dict, svc: ExternalServices = ExternalServices()) -> None:
        super().__init__(data=data, svc=svc)
        self.add_plug(name='kube', container_path='/root/.kube', optional=False, writable=False)
        self.config_schema.update({
            "required": ["manifest"],
            "additionalProperties": True,
            "properties": {
                "timeout_ms": {
                    "description": "How long to wait for the resource to become available after creation/updates? "
                                   "(seconds)",
                    "type": "integer",
                    "minValue": 1000
                },
                "timeout_interval_ms": {
                    "description": "Sleep intervals progressing towards the timeout, in milli-seconds.",
                    "type": "integer",
                    "minValue": 100
                },
                "manifest": {
                    "type": "object",
                    "required": ["metadata"],
                    "additionalProperties": True,
                    "properties": {
                        "apiVersion": {"type": "string", "minLength": 1},
                        "kind": {"type": "string", "minLength": 1},
                        "metadata": {
                            "type": "object",
                            "required": ["name"],
                            "additionalProperties": True,
                            "properties": {
                                "name": {"type": "string", "minLength": 1},
                                "namespace": {"type": "string", "minLength": 1},
                                "annotations": {
                                    "type": "object",
                                    "additionalProperties": True
                                },
                                "labels": {
                                    "type": "object",
                                    "additionalProperties": True
                                }
                            }
                        }
                    }
                }
            }
        })

    @property
    def timeout_ms(self) -> int:
        return self.info.config['timeout_ms'] if 'timeout_ms' in self.info.config else 60 * 5 * 1000

    @property
    def timeout_interval_ms(self) -> int:
        return self.info.config['timeout_interval_ms'] if 'timeout_interval_ms' in self.info.config else 100

    def discover_state(self):
        if 'namespace' in self.info.config['manifest']['metadata']:
            return self.svc.find_k8s_namespace_object(self.info.config['manifest'])
        else:
            return self.svc.find_k8s_cluster_object(self.info.config['manifest'])

    def get_actions_for_missing_state(self) -> Sequence[DAction]:
        manifest = self.info.config['manifest']
        metadata = manifest['metadata']
        return [DAction(name='create', description=f"Create {manifest['kind'].lower()} '{metadata['name']}'")]

    def get_actions_for_discovered_state(self, state: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = []

        differences: list = collect_differences(desired=self.info.config['manifest'], actual=state)
        if 'apiVersion' in differences:
            differences.remove('apiVersion')
        if 'kind' in differences:
            differences.remove('kind')
        if differences:
            if self.info.verbose:
                print("Found state differences: ", file=sys.stderr)
                pprint(differences, stream=sys.stderr)
            kind: str = self.info.config['manifest']['kind']
            name: str = self.info.config['manifest']['metadata']['name']
            actions.append(DAction(name='update', description=f"Update {kind.lower()} '{name}'", args=['update']))

        return actions

    def build_kubectl_manifest(self) -> dict:
        return deepcopy(self.info.config['manifest'])

    @action
    def state(self, args) -> None:
        if self.timeout_interval_ms >= self.timeout_ms:
            raise Exception(f"timeout interval ({self.timeout_interval_ms / 1000}) cannot be greater "
                            f"than or equal to total timeout ({self.timeout_ms / 1000}) duration")
        super().state(args)

    @action
    def create(self, args) -> None:
        if args: pass
        start_ms: int = int(round(time.time() * 1000))
        self.svc.create_k8s_object(self.build_kubectl_manifest(), self.timeout_ms, self.info.verbose)
        finish_ms: int = int(round(time.time() * 1000))
        creation_duration_ms: int = finish_ms - start_ms
        remaining_timeout_ms: int = self.timeout_ms - creation_duration_ms
        timeout_interval_ms: int = self.timeout_interval_ms
        if self.timeout_interval_ms >= remaining_timeout_ms:
            timeout_interval_ms: int = remaining_timeout_ms / 2
        self.check_availability(timeout_ms=remaining_timeout_ms, timeout_interval_ms=timeout_interval_ms)

    @action
    def update(self, args) -> None:
        if args: pass
        start_ms: int = int(round(time.time() * 1000))
        self.svc.update_k8s_object(self.build_kubectl_manifest(), self.timeout_ms, self.info.verbose)
        finish_ms: int = int(round(time.time() * 1000))
        creation_duration_ms: int = finish_ms - start_ms
        remaining_timeout_ms: int = self.timeout_ms - creation_duration_ms
        timeout_interval_ms: int = self.timeout_interval_ms
        if self.timeout_interval_ms >= remaining_timeout_ms:
            timeout_interval_ms: int = remaining_timeout_ms / 2
        self.check_availability(timeout_ms=remaining_timeout_ms, timeout_interval_ms=timeout_interval_ms)

    def is_available(self, state: dict) -> bool:
        return True

    def check_availability(self, timeout_ms: int = None, timeout_interval_ms: int = None):
        if timeout_ms is None:
            timeout_ms: int = self.timeout_ms
        if timeout_interval_ms is None:
            timeout_interval_ms: int = self.timeout_interval_ms

        waited_ms: int = 0
        while waited_ms <= timeout_ms:
            state: dict = self.discover_state()
            if self.is_available(state):
                return True
            sleep(timeout_interval_ms / 1000)
            waited_ms += timeout_interval_ms

        kind: str = self.info.config['manifest']['kind']
        name: str = self.info.config['manifest']['metadata']['name']
        raise TimeoutError(f"timed out waiting for {kind.lower()} '{name}' to become available")
