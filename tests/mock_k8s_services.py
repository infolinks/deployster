from typing import Mapping, Union

from k8s_services import K8sServices


class MockK8sServices(K8sServices):

    def __init__(self, objects: Mapping[str, dict] = None) -> None:
        super().__init__()
        self._objects: Mapping[str, dict] = objects

    def find_cluster_object(self, manifest: dict) -> Union[None, dict]:
        api_version: str = manifest["apiVersion"]
        kind: str = manifest["kind"]
        metadata: dict = manifest["metadata"]
        name: str = metadata["name"]
        key: str = f"{api_version}-{kind}-{name}"
        return self._objects[key] if key in self._objects else None

    def find_namespace_object(self, manifest: dict) -> Union[None, dict]:
        api_version: str = manifest["apiVersion"]
        kind: str = manifest["kind"]
        metadata: dict = manifest["metadata"]
        name: str = metadata["name"]
        namespace: str = metadata["namespace"]
        key = f"{api_version}-{kind}-{namespace}-{name}"
        return self._objects[key] if key in self._objects else None

    def create_object(self, manifest: dict, timeout: int = 60 * 5) -> None:
        pass

    def update_object(self, manifest: dict, timeout: int = 60 * 5) -> None:
        pass
