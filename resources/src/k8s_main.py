#!/usr/bin/env python3.6

import json
import sys
from typing import Mapping

from k8s import K8sResource
from k8s_deployment import K8sDeployment
from k8s_ingress import K8sIngress
from k8s_secret import K8sSecret
from k8s_service import K8sService


def main():
    # mapping between resource types (docker images) and their associated Kubernetes kind & API versions, and the
    # DResource subclass to handle them
    k8s_object_types: Mapping[str, dict] = {
        'infolinks/deployster-k8s-clusterrole': {
            'kind': 'ClusterRole',
            'api_version': 'rbac.authorization.k8s.io/v1',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-clusterrolebinding': {
            'kind': 'ClusterRoleBinding',
            'api_version': 'rbac.authorization.k8s.io/v1',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-configmap': {
            'kind': 'ConfigMap',
            'api_version': 'v1',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-cronjob': {
            'kind': 'CronJob',
            'api_version': 'batch/v1beta1',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-daemonset': {
            'kind': 'DaemonSet',
            'api_version': 'apps/v1beta2',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-deployment': {
            'kind': 'Deployment',
            'api_version': 'apps/v1beta2',
            'factory': K8sDeployment
        },
        'infolinks/deployster-k8s-horizontalpodautoscaler': {
            'kind': 'HorizontalPodAutoscaler',
            'api_version': 'autoscaling/v1',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-ingress': {
            'kind': 'Ingress',
            'api_version': 'extensions/v1beta1',
            'factory': K8sIngress
        },
        'infolinks/deployster-k8s-job': {
            'kind': 'Job',
            'api_version': 'batch/v1',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-namespace': {
            'kind': 'Namespace',
            'api_version': 'v1',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-networkpolicy': {
            'kind': 'NetworkPolicy',
            'api_version': 'networking/v1',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-node': {
            'kind': 'Node',
            'api_version': 'v1',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-persistentvolume': {
            'kind': 'PersistentVolume',
            'api_version': 'v1',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-persistentvolumeclaim': {
            'kind': 'PersistentVolumeClaim',
            'api_version': 'v1',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-pod': {
            'kind': 'Pod',
            'api_version': 'v1',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-replicaset': {
            'kind': 'ReplicaSet',
            'api_version': 'apps/v1beta2',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-replicationcontroller': {
            'kind': 'ReplicationController',
            'api_version': 'v1',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-role': {
            'kind': 'Role',
            'api_version': 'rbac.authorization.k8s.io/v1',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-rolebinding': {
            'kind': 'RoleBinding',
            'api_version': 'rbac.authorization.k8s.io/v1',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-secret': {
            'kind': 'Secret',
            'api_version': 'v1',
            'factory': K8sSecret
        },
        'infolinks/deployster-k8s-service': {
            'kind': 'Service',
            'api_version': 'v1',
            'factory': K8sService
        },
        'infolinks/deployster-k8s-serviceaccount': {
            'kind': 'ServiceAccount',
            'api_version': 'v1',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-statefulset': {
            'kind': 'StatefulSet',
            'api_version': 'apps/v1beta2',
            'factory': K8sResource
        },
        'infolinks/deployster-k8s-storageclass': {
            'kind': 'StorageClass',
            'api_version': 'storage/v1',
            'factory': K8sResource
        },
    }

    # read the current resource type from stdin, along with all the other information Deployster sends
    data = json.loads(sys.stdin.read())
    resource_type: str = data['type'][0:data['type'].find(':')] if ':' in data['type'] else data['type']

    # search for the K8sResource subclass to pass execution to
    for type, info in k8s_object_types.items():
        if resource_type == type:
            if 'config' in data and 'manifest' in data['config']:
                manifest: dict = data['config']['manifest']
                if 'kind' not in manifest:
                    manifest['kind'] = info['kind']
                if 'apiVersion' not in manifest:
                    manifest['apiVersion'] = info['api_version']

            info['factory'](data=data).execute()
            return

    # no resource handler found!
    raise Exception(f"resource type '{data['type']}' is not supported (this should not happen)")


if __name__ == "__main__":
    main()
