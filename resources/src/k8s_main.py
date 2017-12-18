#!/usr/bin/env python3.6

import json
import sys
from typing import Callable, Mapping

from external_services import ExternalServices
from k8s import K8sResource
from k8s_deployment import K8sDeployment
from k8s_ingress import K8sIngress
from k8s_secret import K8sSecret
from k8s_service import K8sService


def main():
    # mapping between resource types (docker images) to the K8sResource subclass to handle it
    k8s_resource_types: Mapping[str, Callable[[dict, ExternalServices], K8sResource]] = {
        "infolinks/deployster-k8s-deployment": K8sDeployment,
        "infolinks/deployster-k8s-ingress": K8sIngress,
        "infolinks/deployster-k8s-secret": K8sSecret,
        "infolinks/deployster-k8s-service": K8sService
    }

    # read the current resource type from stdin, along with all the other information Deployster sends
    data = json.loads(sys.stdin.read())
    resource_type: str = data['type']

    # search for the K8sResource subclass to pass execution to
    for type, resource_ctor in k8s_resource_types.items():
        if resource_type.startswith(type):
            resource_ctor(data=data).execute()
            return

    # no resource handler found; use the default K8sResource class
    K8sResource(data=data).execute()


if __name__ == "__main__":
    main()
