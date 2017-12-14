import json
import subprocess
from typing import Union


class K8sServices:

    def __init__(self) -> None:
        super().__init__()

    def find_cluster_object(self, manifest: dict) -> Union[None, dict]:
        cmd = f"kubectl get {manifest['kind']} {manifest['metadata']['name']} --ignore-not-found=true --output=json"
        process = subprocess.run(f"{cmd}", shell=True, check=True, stdout=subprocess.PIPE)
        return json.loads(process.stdout) if process.stdout else None

    def find_namespace_object(self, manifest: dict) -> Union[None, dict]:
        metadata: dict = manifest['metadata']
        kind: str = manifest['kind']
        name: str = metadata['name']
        namespace: str = metadata['namespace']
        cmd: str = f"kubectl get --namespace {namespace} {kind} {name} --ignore-not-found=true --output=json"
        process = subprocess.run(f"{cmd}", shell=True, check=True, stdout=subprocess.PIPE)
        return json.loads(process.stdout) if process.stdout else None

    def create_object(self, manifest: dict, timeout: int = 60 * 5) -> None:
        subprocess.run(f"kubectl create -f -",
                       input=json.dumps(manifest),
                       encoding='utf-8',
                       check=True,
                       timeout=timeout,
                       shell=True)

    def update_object(self, manifest: dict, timeout: int = 60 * 5) -> None:
        subprocess.run(f"kubectl apply -f -",
                       input=json.dumps(manifest),
                       encoding='utf-8',
                       check=True,
                       timeout=timeout,
                       shell=True)
