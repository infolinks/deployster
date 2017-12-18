from base64 import b64decode
from base64 import b64encode
from copy import deepcopy

from external_services import ExternalServices
from k8s import K8sResource


class K8sSecret(K8sResource):

    def __init__(self, data: dict, svc: ExternalServices = ExternalServices()) -> None:
        super().__init__(data=data, svc=svc)

    def discover_state(self):
        manifest = super().discover_state()
        if manifest is not None and 'data' in manifest and manifest['data'] is not None:
            manifest = deepcopy(manifest)
            manifest['data'] = {key: b64decode(str(val).encode()).decode() for key, val in manifest['data'].items()}
        return manifest

    def build_kubectl_manifest(self) -> dict:
        manifest: dict = super().build_kubectl_manifest()

        # overwrite with encoded data
        manifest['data'] = {key: b64encode(str(val).encode()).decode() for key, val in manifest['data'].items()}
        return manifest
