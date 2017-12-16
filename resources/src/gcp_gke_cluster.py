#!/usr/bin/env python3.6

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Mapping, Sequence, MutableSequence

import yaml

from dresources import DAction, action
from external_services import ExternalServices
from gcp import GcpResource

DEFAULT_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/compute",
    "https://www.googleapis.com/auth/devstorage.read_only",
    "https://www.googleapis.com/auth/logging.write",
    "https://www.googleapis.com/auth/monitoring"
]


class GkeCluster(GcpResource):

    def __init__(self, data: dict, svc: ExternalServices = ExternalServices()) -> None:
        super().__init__(data=data, svc=svc)
        self.add_plug(name='kube', container_path='/root/.kube', optional=False, writable=True)
        self.config_schema.update({
            "type": "object",
            "required": ["project_id", "zone", "name", "description", "version", "node_pools"],
            "additionalProperties": False,
            "properties": {
                "project_id": {"type": "string"},
                "zone": {"type": "string"},
                "name": {"type": "string"},
                "description": {"type": "string"},
                "version": {"type": "string"},
                "node_pools": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string"},
                            "min_size": {"type": "integer", "minValue": 1},
                            "max_size": {"type": "integer", "minValue": 1},
                            "service_account": {"type": "string"},
                            "oauth_scopes": {
                                "type": "array",
                                "items": {"type": "string", "uniqueItems": True}
                            },
                            "preemptible": {"type": "boolean"},
                            "machine_type": {"type": "string"},
                            "disk_size_gb": {"type": "integer"},
                            "tags": {
                                "type": "array",
                                "items": {"type": "string", "uniqueItems": True}
                            },
                            "metadata": {"type": "object"},
                            "labels": {"type": "object"}
                        }
                    }
                }
            }
        })

    def authenticate(self, properties: dict) -> None:
        sa_plug = self.get_plug('gcp-service-account')

        # generate a kubectl config file using the cluster properties and the service account's access token
        cluster_full_id = f"gke_{self.info.config['project_id']}_{self.info.config['zone']}_{self.info.config['name']}"
        os.makedirs(self.get_plug('kube').container_path, exist_ok=True)
        with open(self.get_plug('kube').container_path + '/config', 'w') as stream:
            stream.write(yaml.dump({
                'apiVersion': 'v1',
                'kind': 'Config',
                'preferences': {},
                'clusters': [
                    {
                        'name': cluster_full_id,
                        'cluster': {
                            'certificate-authority-data': properties['masterAuth']['clusterCaCertificate'],
                            'server': f"https://{properties['endpoint']}"
                        }
                    }
                ],
                'users': [
                    {
                        'name': cluster_full_id,
                        'user': {
                            'token': self.svc.generate_gcloud_access_token(Path(sa_plug.container_path))
                        }
                    }
                ],
                'contexts': [
                    {
                        'name': cluster_full_id,
                        'context': {
                            'cluster': cluster_full_id,
                            'user': cluster_full_id
                        }
                    }
                ],
                'current-context': cluster_full_id
            }))

    def discover_state(self):
        desired_version: str = self.info.config['version']
        if not self.is_version_master_valid(desired_version):
            raise Exception(f"version '{desired_version}' is not supported as a master version in GKE")
        elif not self.is_version_node_valid(desired_version):
            raise Exception(f"version '{desired_version}' is not supported as a node version in GKE")
        else:
            return self.svc.get_gke_cluster(project_id=self.info.config['project_id'],
                                            zone=self.info.config['zone'],
                                            name=self.info.config['name'])

    def get_actions_for_missing_state(self) -> Sequence[DAction]:
        return [DAction(name=f"create-cluster", description=f"Create cluster '{self.info.config['name']}'")]

    def get_actions_for_discovered_state(self, state: dict) -> Sequence[DAction]:
        cluster_name = self.info.config['name']
        actions: MutableSequence[DAction] = []
        actual_cluster = state

        # validate cluster is RUNNING
        if actual_cluster['status'] != "RUNNING":
            raise Exception(f"Cluster exists, but not running ('{actual_cluster['status']}')")

        # validate cluster primary zone & locations
        desired_cluster_zone = self.info.config['zone']
        actual_cluster_locations: Sequence[str] = actual_cluster['locations']
        if [desired_cluster_zone] != actual_cluster_locations:
            raise Exception(
                f"Cluster locations are {actual_cluster_locations} instead of {[desired_cluster_zone]}. "
                f"Updating this is not allowed in GKE APIs unfortunately.")

        # validate cluster master version & cluster node pools version
        actual_cluster_master_version: str = actual_cluster["currentMasterVersion"]
        actual_cluster_node_version: str = actual_cluster["currentNodeVersion"]
        desired_version = self.info.config['version']
        if desired_version != actual_cluster_master_version:
            actions.append(
                DAction(name='update-cluster-master-version',
                        description=f"Update master version for cluster '{cluster_name}'"))
        if desired_version != actual_cluster_node_version:
            raise Exception(
                f"Cluster node version is '{actual_cluster_node_version}' instead of '{desired_version}'. "
                f"Updating this is not allowed in GKE APIs unfortunately.")

        # ensure master authorized networks is disabled
        if 'masterAuthorizedNetworksConfig' in actual_cluster:
            if 'enabled' in actual_cluster['masterAuthorizedNetworksConfig']:
                if actual_cluster['masterAuthorizedNetworksConfig']['enabled']:
                    actions.append(
                        DAction(name='disable-master-authorized-networks',
                                description=f"Disable master authorized networks for cluster '{cluster_name}'"))

        # ensure that legacy ABAC is disabled
        if 'legacyAbac' in actual_cluster:
            if 'enabled' in actual_cluster['legacyAbac']:
                if actual_cluster['legacyAbac']['enabled']:
                    actions.append(
                        DAction(name='disable-legacy-abac',
                                description=f"Disable legacy ABAC for cluster '{cluster_name}'"))

        # ensure monitoring service is set to GKE's monitoring service
        actual_monitoring_service = \
            actual_cluster["monitoringService"] if "monitoringService" in actual_cluster else None
        if actual_monitoring_service != "monitoring.googleapis.com":
            actions.append(
                DAction(name='enable-monitoring-service',
                        description=f"Enable GCP monitoring for cluster '{cluster_name}'"))

        # ensure logging service is set to GKE's logging service
        actual_logging_service = \
            actual_cluster["loggingService"] if "loggingService" in actual_cluster else None
        if actual_logging_service != "logging.googleapis.com":
            actions.append(
                DAction(name='enable-logging-service',
                        description=f"Enable GCP logging for cluster '{cluster_name}'"))

        # infer actual addons status
        actual_addons: dict = actual_cluster["addonsConfig"] if "addonsConfig" in actual_cluster else {}

        # ensure HTTP load-balancing addon is ENABLED
        http_lb_addon: dict = actual_addons["httpLoadBalancing"] if "httpLoadBalancing" in actual_addons else {}
        if 'disabled' in http_lb_addon and http_lb_addon["disabled"]:
            actions.append(
                DAction(name='enable-http-load-balancer-addon',
                        description=f"Enable HTTP load-balancing addon for cluster '{cluster_name}'",
                        args=['set_addon_status', 'httpLoadBalancing', 'enabled']))

        # ensure Kubernetes Dashboard addon is DISABLED
        k8s_dashboard_addon = actual_addons["kubernetesDashboard"] if "kubernetesDashboard" in actual_addons else {}
        if "disabled" in k8s_dashboard_addon and not k8s_dashboard_addon["disabled"]:
            actions.append(
                DAction(name='disable-k8s-dashboard-addon',
                        description=f"Disable legacy Kubernetes Dashboard addon for cluster '{cluster_name}'",
                        args=['set_addon_status', 'kubernetesDashboard', 'disabled']))

        # ensure Horizontal Pod Auto-scaling addon is ENABLED
        horiz_pod_auto_scaling_addon = \
            actual_addons["horizontalPodAutoscaling"] if "horizontalPodAutoscaling" in actual_addons else {}
        if "disabled" in horiz_pod_auto_scaling_addon and horiz_pod_auto_scaling_addon["disabled"]:
            actions.append(
                DAction(name='enable-k8s-horiz-pod-auto-scaling-addon',
                        description=f"Enable horizontal Pod auto-scaling addon for cluster '{cluster_name}'",
                        args=['set_addon_status', 'horizontalPodAutoscaling', 'enabled']))

        # ensure alpha features are DISABLED
        if 'enableKubernetesAlpha' in actual_cluster and actual_cluster["enableKubernetesAlpha"]:
            raise Exception(f"Cluster alpha features are enabled instead of disabled. "
                            f"Updating this is not allowed in GKE APIs unfortunately.")

        # validate node pools state
        desired_node_pools: Sequence[dict] = self.info.config['node_pools']
        for pool in desired_node_pools:
            pool_name = pool['name']
            actual_pool = self.svc.get_gke_cluster_node_pool(project_id=self.info.config['project_id'],
                                                             zone=desired_cluster_zone,
                                                             name=self.info.config['name'],
                                                             pool_name=pool_name)
            if actual_pool is None:
                actions.append(DAction(name='create-node-pool',
                                       description=f"Create node pool '{pool_name}' in cluster '{cluster_name}'",
                                       args=['create_node_pool', pool_name]))
                continue

            # ensure the node pool is RUNNING
            if actual_pool['status'] != "RUNNING":
                raise Exception(f"Node pool '{pool_name}' exists, but not running ('{actual_pool['status']}')")

            # validate node pool version
            if desired_version != actual_pool["version"]:
                actions.append(
                    DAction(name='update-node-pool-version',
                            description=f"Update version of node pool '{pool_name}' in cluster '{cluster_name}'",
                            args=['update_node_pool_version', pool_name]))

            # infer node pool management features
            management: dict = actual_pool["management"] if "management" in actual_pool else {}

            # ensure auto-repair is ENABLED
            if "autoRepair" not in management or not management["autoRepair"]:
                actions.append(DAction(
                    name='enable-node-pool-autorepair',
                    description=f"Enable auto-repair for node pool '{pool_name}' in cluster '{cluster_name}'",
                    args=['enable_node_pool_autorepair', pool_name]))

            # ensure auto-upgrade is DISABLED
            if "autoUpgrade" in management and management["autoUpgrade"]:
                actions.append(DAction(
                    name='disable-node-pool-autoupgrade',
                    description=f"Disable auto-upgrade for node pool '{pool_name}' in cluster '{cluster_name}'",
                    args=['disable_node_pool_autoupgrade', pool_name]))

            # validate auto-scaling
            desired_pool_min_size: int = pool['min_size'] if 'min_size' in pool else 1
            desired_pool_max_size: int = pool['max_size'] if 'max_size' in pool else desired_pool_min_size
            actual_autoscaling: dict = actual_pool["autoscaling"] if "autoscaling" in actual_pool else {}
            actual_autoscaling_enabled: bool = "enabled" in actual_autoscaling and actual_autoscaling["enabled"]
            actual_autoscaling_min_size: int = actual_autoscaling["minNodeCount"] \
                if "minNodeCount" in actual_autoscaling else None
            actual_autoscaling_max_size: int = actual_autoscaling["maxNodeCount"] \
                if "maxNodeCount" in actual_autoscaling else None
            if not actual_autoscaling_enabled \
                    or actual_autoscaling_min_size != desired_pool_min_size \
                    or actual_autoscaling_max_size != desired_pool_max_size:
                actions.append(
                    DAction(
                        name='configure-node-pool-autoscaling',
                        description=f"Configure auto-scaling of node pool '{pool_name}' in cluster '{cluster_name}'",
                        args=['configure_node_pool_autoscaling',
                              pool_name,
                              str(desired_pool_min_size),
                              str(desired_pool_max_size)]))

            # infer node VM configuration
            pool_cfg: dict = actual_pool['config'] if 'config' in actual_pool else {}

            # validate node pool service account
            if 'service_account' in pool:
                desired_service_account: str = pool['service_account']
                actual_service_account: str = pool_cfg[
                    'serviceAccount'] if 'serviceAccount' in pool_cfg else 'default'
                if desired_service_account != actual_service_account:
                    raise Exception(
                        f"Node pool '{pool_name}' service account is '{actual_service_account}' instead of "
                        f"'{desired_service_account}' (updating the service account is not allowed in GKE APIs)")

            # validate node pool OAuth scopes
            if 'oauth_scopes' in pool:
                desired_oauth_scopes: Sequence[str] = pool['oauth_scopes']
                actual_oauth_scopes: Sequence[str] = pool_cfg["oauthScopes"] if 'oauthScopes' in pool_cfg else []
                if desired_oauth_scopes != actual_oauth_scopes:
                    raise Exception(
                        f"Node pool '{pool_name}' OAuth scopes are {actual_oauth_scopes} instead of "
                        f"{desired_oauth_scopes} (updating OAuth scopes is not allowed in GKE APIs unfortunately)")

            # validate node pool preemptible usage
            if 'preemptible' in pool:
                desired_preemptible: bool = pool['preemptible']
                actual_preemptible: bool = pool_cfg['preemptible'] if 'preemptible' in pool_cfg else False
                if desired_preemptible != actual_preemptible:
                    raise Exception(f"GKE node pools APIs do not allow enabling/disabling preemptibles usage mode "
                                    f"(required for node pool '{pool_name}' in cluster '{cluster_name}')")

            # validate machine type
            if 'machine_type' in pool:
                desired_machine_type: str = pool['machine_type']
                actual_machine_type: str = pool_cfg["machineType"] if "machineType" in pool_cfg else 'n1-standard-1'
                if desired_machine_type != actual_machine_type:
                    raise Exception(
                        f"Node pool '{pool_name}' uses '{actual_machine_type}' instead of '{desired_machine_type}'. "
                        f"Updating this is not allowed in GKE APIs unfortunately.")

            # validate machine disk type
            if 'disk_size_gb' in pool:
                desired_disk_size_gb: int = pool['disk_size_gb']
                actual_disk_size_gb: int = pool_cfg["diskSizeGb"] if "diskSizeGb" in pool_cfg else 100
                if desired_disk_size_gb != actual_disk_size_gb:
                    raise Exception(
                        f"Node pool '{pool_name}' allocates {actual_disk_size_gb}GB disk space instead of "
                        f"{desired_disk_size_gb}GB. Updating this is not allowed in GKE APIs unfortunately.")

            # validate network tags
            if 'tags' in pool:
                desired_tags: Sequence[str] = pool['tags']
                actual_tags: Sequence[str] = pool_cfg["tags"] if "tags" in pool_cfg else []
                if desired_tags != actual_tags:
                    raise Exception(
                        f"Node pool '{pool_name}' network tags are '{actual_tags}' instead of '{desired_tags}'. "
                        f"Updating this is not allowed in GKE APIs unfortunately.")

            # validate GCE metadata
            if 'metadata' in pool:
                desired_metadata: Mapping[str, str] = pool['metadata']
                actual_metadata: Mapping[str, str] = pool_cfg["metadata"] if "metadata" in pool_cfg else {}
                if desired_metadata != actual_metadata:
                    raise Exception(
                        f"Node pool '{pool_name}' GCE metadata is '{actual_metadata}' instead of '{desired_metadata}'. "
                        f"Updating this is not allowed in GKE APIs unfortunately.")

            # validate Kubernetes labels
            if 'labels' in pool:
                desired_labels: Mapping[str, str] = pool['labels']
                actual_labels: Mapping[str, str] = pool_cfg["labels"] if "labels" in pool_cfg else {}
                if desired_labels != actual_labels:
                    raise Exception(
                        f"Node pool '{pool_name}' Kubernetes labels are '{actual_labels}' instead of "
                        f"'{desired_labels}'. Updating this is not allowed in GKE APIs unfortunately.")

        if not actions:
            # if no actions returned, we are VALID - create authentication for dependant resources
            self.authenticate(properties=state)

        return actions

    def configure_action_argument_parser(self, action: str, argparser: argparse.ArgumentParser):
        super().configure_action_argument_parser(action, argparser)
        if action == 'set_addon_status':
            argparser.add_argument('addon', metavar='ADDON', help="name of the add-on to enable/disable")
            argparser.add_argument('status', metavar='STATUS', choices=['enabled', 'disabled'],
                                   help="either 'enabled' or 'disabled'")
        elif action == 'create_node_pool':
            argparser.add_argument('pool', metavar='POOL-NAME', help="name of the node pool to create")
        elif action == 'update_node_pool_version':
            argparser.add_argument('pool', metavar='POOL-NAME', help="name of the node pool to update")
        elif action == 'enable_node_pool_autorepair':
            argparser.add_argument('pool', metavar='POOL-NAME', help="name of the node pool to update")
        elif action == 'disable_node_pool_autoupgrade':
            argparser.add_argument('pool', metavar='POOL-NAME', help="name of the node pool to update")
        elif action == 'configure_node_pool_autoscaling':
            argparser.add_argument('pool', metavar='POOL-NAME', help="name of the node pool to update")
            argparser.add_argument('min_size', type=int, metavar='MIN-SIZE', help="minimum size of nodes in the pool")
            argparser.add_argument('max_size', type=int, metavar='MAX-SIZE', help="maximum size of nodes in the pool")

    def is_version_master_valid(self, version) -> bool:
        config = self.svc.get_gke_server_config(project_id=self.info.config['project_id'],
                                                zone=self.info.config['zone'])
        return version in config['validMasterVersions']

    def is_version_node_valid(self, version) -> bool:
        config = self.svc.get_gke_server_config(project_id=self.info.config['project_id'],
                                                zone=self.info.config['zone'])
        return version in config['validNodeVersions']

    @action
    def create_cluster(self, args):
        if args: pass
        desired_version: str = self.info.config['version']

        def build_node_pool(pool: dict):
            min_node_count = pool['min_size'] if 'min_size' in pool else 1
            return {
                "name": pool['name'],
                "version": desired_version,
                "management": {"autoRepair": True, "autoUpgrade": False},
                "initialNodeCount": min_node_count,
                "autoscaling": {
                    "minNodeCount": min_node_count,
                    "enabled": True,
                    "maxNodeCount": pool['max_size'] if 'max_size' in pool else min_node_count,
                },
                "config": {
                    "serviceAccount": pool['service_account'] if 'service_account' in pool else None,
                    "oauthScopes": pool['oauth_scopes'] if 'oauth_scopes' in pool else DEFAULT_OAUTH_SCOPES,
                    "preemptible": pool['preemptible'] if 'preemptible' in pool else True,
                    "machineType": pool['machine_type'] if 'machine_type' in pool else 'n1-standard-1',
                    "diskSizeGb": pool['disk_size_gb'] if 'disk_size_gb' in pool else 20,
                    "tags": pool['tags'] if 'tags' in pool else [],  # GCE network tags
                    "metadata": pool['metadata'] if 'metadata' in pool else {},  # GKE nodes metadata entries
                    "labels": pool['labels'] if 'labels' in pool else {},  # k8s labels to apply to nodes
                }
            }

        cluster_config = {
            "cluster": {
                "name": self.info.config['name'],
                "description": self.info.config['description'],
                "locations": [self.info.config['zone']],
                "initialClusterVersion": self.info.config['version'],
                "masterAuth": {"username": ""},
                "masterAuthorizedNetworksConfig": {"enabled": False},
                "legacyAbac": {"enabled": False},
                "monitoringService": "monitoring.googleapis.com",
                "loggingService": "logging.googleapis.com",
                "addonsConfig": {
                    "httpLoadBalancing": {"disabled": False},
                    "kubernetesDashboard": {"disabled": True},
                    "horizontalPodAutoscaling": {"disabled": False},
                },
                "enableKubernetesAlpha": False,
                "nodePools": [build_node_pool(pool) for pool in self.info.config['node_pools']]
            },
        }

        self.svc.create_gke_cluster(project_id=self.info.config['project_id'],
                                    zone=self.info.config['zone'],
                                    body=cluster_config)

    @action
    def update_cluster_master_version(self, args):
        if args: pass
        self.svc.update_gke_cluster_master_version(project_id=self.info.config['project_id'],
                                                   zone=self.info.config['zone'],
                                                   name=self.info.config['name'],
                                                   version=self.info.config['version'])

    @action
    def disable_master_authorized_networks(self, args):
        if args: pass
        self.svc.update_gke_cluster(project_id=self.info.config['project_id'],
                                    zone=self.info.config['zone'],
                                    name=self.info.config['name'],
                                    body={'update': {'desiredMasterAuthorizedNetworksConfig': {'enabled': False}}})

    @action
    def disable_legacy_abac(self, args):
        if args: pass
        self.svc.update_gke_cluster_legacy_abac(project_id=self.info.config['project_id'],
                                                zone=self.info.config['zone'],
                                                name=self.info.config['name'],
                                                body={'enabled': False})

    @action
    def enable_monitoring_service(self, args):
        if args: pass
        self.svc.update_gke_cluster_monitoring(project_id=self.info.config['project_id'],
                                               zone=self.info.config['zone'],
                                               name=self.info.config['name'],
                                               body={'monitoringService': "monitoring.googleapis.com"})

    @action
    def enable_logging_service(self, args):
        if args: pass
        self.svc.update_gke_cluster_logging(project_id=self.info.config['project_id'],
                                            zone=self.info.config['zone'],
                                            name=self.info.config['name'],
                                            body={'loggingService': "logging.googleapis.com"})

    @action
    def set_addon_status(self, args):
        self.svc.update_gke_cluster_addons(project_id=self.info.config['project_id'],
                                           zone=self.info.config['zone'],
                                           name=self.info.config['name'],
                                           body={'addonsConfig': {args.addon: {'disabled': args.status == 'disabled'}}})

    @action
    def create_node_pool(self, args):
        pool: dict = next(pool for pool in self.info.config['node_pools'] if pool['name'] == args.pool)
        min_node_count = pool['min_size'] if 'min_size' in pool else 1
        pool_config = {
            "name": args.pool,
            "management": {"autoRepair": True, "autoUpgrade": False},
            "initialNodeCount": min_node_count,
            "autoscaling": {
                "minNodeCount": min_node_count,
                "enabled": True,
                "maxNodeCount": pool['max_size'] if 'max_size' in pool else min_node_count,
            },
            "config": {
                "serviceAccount": pool['service_account'] if 'service_account' in pool else None,
                "oauthScopes": pool['oauth_scopes'] if 'oauth_scopes' in pool else DEFAULT_OAUTH_SCOPES,
                "preemptible": pool['preemptible'] if 'preemptible' in pool else True,
                "machineType": pool['machine_type'] if 'machine_type' in pool else 'n1-standard-1',
                "diskSizeGb": pool['disk_size_gb'] if 'disk_size_gb' in pool else 20,
                "tags": pool['tags'] if 'tags' in pool else [],  # GCE network tags
                "metadata": pool['metadata'] if 'metadata' in pool else {},  # GKE nodes metadata entries
                "labels": pool['labels'] if 'labels' in pool else {},  # k8s labels to apply to nodes
            }
        }

        self.svc.create_gke_cluster_node_pool(project_id=self.info.config['project_id'],
                                              zone=self.info.config['zone'],
                                              name=self.info.config['name'],
                                              node_pool_body={"nodePool": pool_config})

    @action
    def update_node_pool_version(self, args):
        self.svc.update_gke_cluster_node_pool(project_id=self.info.config['project_id'],
                                              zone=self.info.config['zone'],
                                              cluster_name=self.info.config['name'],
                                              pool_name=args.pool,
                                              body={"nodeVersion": self.info.config['version']})

    @action
    def enable_node_pool_autorepair(self, args):
        self.svc.update_gke_cluster_node_pool_management(project_id=self.info.config['project_id'],
                                                         zone=self.info.config['zone'],
                                                         cluster_name=self.info.config['name'],
                                                         pool_name=args.pool,
                                                         body={"management": {"autoRepair": True}})

    @action
    def disable_node_pool_autoupgrade(self, args):
        self.svc.update_gke_cluster_node_pool_management(project_id=self.info.config['project_id'],
                                                         zone=self.info.config['zone'],
                                                         cluster_name=self.info.config['name'],
                                                         pool_name=args.pool,
                                                         body={"management": {"autoUpgrade": False}})

    @action
    def configure_node_pool_autoscaling(self, args):
        self.svc.update_gke_cluster_node_pool_autoscaling(project_id=self.info.config['project_id'],
                                                          zone=self.info.config['zone'],
                                                          cluster_name=self.info.config['name'],
                                                          pool_name=args.pool,
                                                          body={
                                                              'autoscaling': {
                                                                  'enabled': True,
                                                                  'minNodeCount': args.min_size,
                                                                  'maxNodeCount': args.max_size
                                                              }
                                                          })


def main():
    GkeCluster(data=json.loads(sys.stdin.read())).execute()  # pragma: no cover


if __name__ == "__main__":
    main()
