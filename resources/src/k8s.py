from copy import deepcopy
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
                "timeout": {"type": "integer", "minValue": 1},
                "timeout_interval": {"type": "integer", "minValue": 1},
                "manifest": {
                    "type": "object",
                    "required": ["apiVersion", "kind", "metadata"],
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
    def timeout(self) -> int:
        return self.info.config['timeout'] if 'timeout' in self.info.config else 60 * 5

    @property
    def timeout_interval(self) -> int:
        return self.info.config['timeout_interval'] if 'timeout_interval' in self.info.config else 5

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

        differences: Sequence[str] = collect_differences(desired=self.info.config['manifest'], actual=state)
        if differences:
            kind: str = self.info.config['manifest']['kind']
            name: str = self.info.config['manifest']['metadata']['name']
            actions.append(DAction(name='update', description=f"Update {kind} '{name}'", args=['update']))

        return actions

    def build_kubectl_manifest(self) -> dict:
        return deepcopy(self.info.config['manifest'])

    @action
    def create(self, args) -> None:
        if args: pass
        self.svc.create_k8s_object(self.build_kubectl_manifest(), self.timeout)
        self.check_availability()

    @action
    def update(self, args) -> None:
        if args: pass
        self.svc.update_k8s_object(self.build_kubectl_manifest(), self.timeout)
        self.check_availability()

    def is_available(self, state: dict) -> bool:
        return True

    def check_availability(self):
        # TODO: consider waiting for kube-lego to generate the TLS certificate from LetsEncrypt (if it's installed)

        waited = 0
        while waited < self.timeout:
            state: dict = self.discover_state()
            if self.is_available(state):
                return True
            sleep(self.timeout_interval)
            waited += self.timeout_interval

        kind: str = self.info.config['manifest']['kind']
        name: str = self.info.config['manifest']['metadata']['name']
        raise TimeoutError(f"timed out waiting for {kind} '{name}' to become available")
