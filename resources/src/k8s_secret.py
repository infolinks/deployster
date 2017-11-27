#!/usr/bin/env python3

import base64
import json
import sys
from typing import Mapping

from k8s_configmap import K8sConfigMap


class K8sSecret(K8sConfigMap):

    @property
    def k8s_kind(self) -> str:
        return "Secret"

    def build_creation_manifest(self) -> dict:
        # overwrite with encoded data
        manifest: dict = super().build_creation_manifest()
        manifest['data'] = self.data
        return manifest

    @property
    def data(self) -> Mapping[str, str]:
        return {key: base64.b64encode(str(val).encode()).decode() for key, val in super().data.items()}


def main():
    K8sSecret(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
