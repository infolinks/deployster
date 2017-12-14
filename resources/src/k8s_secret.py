from base64 import b64encode

from k8s import K8sResource
from k8s_services import K8sServices


class K8sSecret(K8sResource):

    def __init__(self, data: dict, k8s_services: K8sServices = K8sServices()) -> None:
        super().__init__(data, k8s_services)

    def build_kubectl_manifest(self) -> dict:
        manifest: dict = super().build_kubectl_manifest()

        # overwrite with encoded data
        manifest['data'] = {key: b64encode(str(val).encode()).decode() for key, val in manifest['data'].items()}
        return manifest
