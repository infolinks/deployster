#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
from subprocess import PIPE
from typing import Mapping, Sequence, MutableSequence

import yaml
from googleapiclient.errors import HttpError

from dresources import DAction, action
from gcp import GcpResource
from gcp_project import GcpProject
from gcp_services import get_container, wait_for_container_projects_zonal_operation

DEFAULT_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/compute",
    "https://www.googleapis.com/auth/devstorage.read_only",
    "https://www.googleapis.com/auth/logging.write",
    "https://www.googleapis.com/auth/monitoring"
]


class GkeCluster(GcpResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.add_dependency(name='project', type='infolinks/deployster-gcp-project', optional=False, factory=GcpProject)
        self.add_plug(name='kube', container_path='/root/.kube', optional=False, writable=True)
        self.config_schema.update({
            "type": "object",
            "required": ["zone", "name", "description", "node_pools"],
            "additionalProperties": False,
            "properties": {
                "zone": {"type": "string"},
                "name": {"type": "string"},
                "description": {"type": "string"},
                "version": {"type": "string"},
                "node_pools": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string"},
                            "min_size": {"type": "integer"},
                            "max_size": {"type": "integer"},
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

    @property
    def project(self) -> GcpProject:
        return self.get_dependency('project')

    @property
    def zone(self) -> str:
        return self.resource_config['zone']

    @property
    def name(self) -> str:
        return self.resource_config['name']

    @property
    def description(self) -> str:
        return self.resource_config['description']

    @property
    def version(self) -> str:
        return self.resource_config['version']

    @property
    def node_pools(self) -> Sequence[dict]:
        return self.resource_config['node_pools']

    def authenticate(self, properties: dict) -> None:
        # generate a kubectl config file using the cluster properties and the service account's access token
        sa_plug = self.get_plug('gcp-service-account')

        # first, make gcloud use our service account
        command = f"gcloud auth activate-service-account --key-file={sa_plug.container_path}"
        subprocess.run(command, check=True, shell=True)

        # extract our service account's GCP access token
        process = subprocess.run(f"gcloud auth print-access-token", check=True, shell=True, stdout=PIPE)
        access_token: str = process.stdout.decode('utf-8').strip()

        # update the user object to use the gcloud access token instead of GCP helper, then write back to the file
        cluster_full_id = f"gke_{self.project.project_id}_{self.zone}_{self.name}"
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
                            'token': access_token
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

    def discover_actual_properties(self):
        clusters_service = get_container().projects().zones().clusters()
        try:
            return clusters_service.get(projectId=self.project.project_id,
                                        zone=self.zone,
                                        clusterId=self.name).execute()
        except HttpError as e:
            if e.resp.status == 404:
                return None
            else:
                raise

    def get_actions_when_missing(self) -> Sequence[DAction]:
        return [DAction(name=f"create-cluster", description=f"Create cluster '{self.name}'")]

    def get_actions_when_existing(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = []
        actual_cluster = actual_properties

        # validate cluster is RUNNING
        if actual_cluster['status'] != "RUNNING":
            raise Exception(f"Cluster exists, but not running ('{actual_cluster['status']}')")

        # validate cluster primary zone & locations
        actual_cluster_zone: str = actual_cluster['zone']
        actual_cluster_locations: Sequence[str] = actual_cluster['locations']
        if self.zone != actual_cluster_zone:
            raise Exception(
                f"Cluster primary zone is '{actual_cluster_zone}' instead of '{self.zone}'. "
                f"Updating this is not allowed in GKE APIs unfortunately.")
        elif [self.zone] != actual_cluster_locations:
            raise Exception(
                f"Cluster locations are '{actual_cluster_locations}' instead of '{[self.zone]}'. "
                f"Updating this is not allowed in GKE APIs unfortunately.")

        # validate cluster master version & cluster node pools version
        actual_cluster_master_version: str = actual_cluster["currentMasterVersion"]
        actual_cluster_node_version: str = actual_cluster["currentNodeVersion"]
        if self.version != actual_cluster_master_version:
            actions.append(
                DAction(name='update-cluster-master-version',
                        description=f"Update master version for cluster '{self.name}'"))
        if self.version != actual_cluster_node_version:
            raise Exception(
                f"Cluster node version is '{actual_cluster_node_version}' instead of '{self.version}'. "
                f"Updating this is not allowed in GKE APIs unfortunately.")

        # ensure master authorized networks is disabled
        if 'masterAuthorizedNetworksConfig' in actual_cluster:
            if 'enabled' in actual_cluster['masterAuthorizedNetworksConfig']:
                if actual_cluster['masterAuthorizedNetworksConfig']['enabled']:
                    actions.append(
                        DAction(name='disable-master-authorized-networks',
                                description=f"Disable master authorized networks for cluster '{self.name}'"))

        # ensure that legacy ABAC is disabled
        if 'legacyAbac' in actual_cluster:
            if 'enabled' in actual_cluster['legacyAbac']:
                if actual_cluster['legacyAbac']['enabled']:
                    actions.append(
                        DAction(name='disable-legacy-abac',
                                description=f"Disable legacy ABAC for cluster '{self.name}'"))

        # ensure monitoring service is set to GKE's monitoring service
        actual_monitoring_service = \
            actual_cluster["monitoringService"] if "monitoringService" in actual_cluster else None
        if actual_monitoring_service != "monitoring.googleapis.com":
            actions.append(
                DAction(name='enable-monitoring-service',
                        description=f"Enable GCP monitoring for cluster '{self.name}'"))

        # ensure logging service is set to GKE's logging service
        actual_logging_service = \
            actual_cluster["loggingService"] if "loggingService" in actual_cluster else None
        if actual_logging_service != "logging.googleapis.com":
            actions.append(
                DAction(name='enable-logging-service',
                        description=f"Enable GCP logging for cluster '{self.name}'"))

        # infer actual addons status
        actual_addons: dict = actual_cluster["addonsConfig"] if "addonsConfig" in actual_cluster else {}

        # ensure HTTP load-balancing addon is ENABLED
        http_lb_addon: dict = actual_addons["httpLoadBalancing"] if "httpLoadBalancing" in actual_addons else {}
        if 'disabled' in http_lb_addon and http_lb_addon["disabled"]:
            actions.append(
                DAction(name='enable-http-load-balancer-addon',
                        description=f"Enable HTTP load-balancing addon for cluster '{self.name}'",
                        args=['set_addon_status', 'httpLoadBalancing', 'enabled']))

        # ensure Kubernetes Dashboard addon is DISABLED
        k8s_dashboard_addon = actual_addons["kubernetesDashboard"] if "kubernetesDashboard" in actual_addons else {}
        if "disabled" in k8s_dashboard_addon and not k8s_dashboard_addon["disabled"]:
            actions.append(
                DAction(name='disable-k8s-dashboard-addon',
                        description=f"Disable legacy Kubernetes Dashboard addon for cluster '{self.name}'",
                        args=['set_addon_status', 'kubernetesDashboard', 'disabled']))

        # ensure Horizontal Pod Auto-scaling addon is ENABLED
        horiz_pod_auto_scaling_addon = \
            actual_addons["horizontalPodAutoscaling"] if "horizontalPodAutoscaling" in actual_addons else {}
        if "disabled" in horiz_pod_auto_scaling_addon and horiz_pod_auto_scaling_addon["disabled"]:
            actions.append(
                DAction(name='enable-k8s-horiz-pod-auto-scaling-addon',
                        description=f"Enable horizontal Pod auto-scaling addon for cluster '{self.name}'",
                        args=['set_addon_status', 'horizontalPodAutoscaling', 'enabled']))

        # ensure alpha features are DISABLED
        if 'enableKubernetesAlpha' in actual_cluster and actual_cluster["enableKubernetesAlpha"]:
            raise Exception(f"Cluster alpha features are enabled instead of disabled. "
                            f"Updating this is not allowed in GKE APIs unfortunately.")

        # validate node pools state
        for pool in self.node_pools:
            pool_name = pool['name']
            try:
                actual_pool = \
                    get_container().projects().zones().clusters().nodePools().get(projectId=self.project.project_id,
                                                                                  zone=self.zone,
                                                                                  clusterId=self.name,
                                                                                  nodePoolId=pool_name).execute()
            except HttpError as e:
                if e.resp.status == 404:
                    actions.append(
                        DAction(name='create-node-pool',
                                description=f"'Create node pool '{pool_name}' in cluster '{self.name}'",
                                args=['create_node_pool', pool_name]))
                    continue
                else:
                    raise

            # ensure the node pool is RUNNING
            if actual_pool['status'] != "RUNNING":
                raise Exception(f"Node pool '{pool_name}' exists, but not running ('{actual_pool['status']}')")

            # validate node pool version
            if self.version != actual_pool["version"]:
                actions.append(
                    DAction(name='update-node-pool-version',
                            description=f"Update version of node pool '{pool_name}' in cluster '{self.name}'",
                            args=['update_node_pool_version', pool_name]))

            # infer node pool management features
            management: dict = actual_pool["management"] if "management" in actual_pool else {}

            # ensure auto-repair is ENABLED
            if "autoRepair" not in management or not management["autoRepair"]:
                actions.append(DAction(
                    name='enable-node-pool-autorepair',
                    description=f"Enable auto-repair for node pool '{pool_name}' in cluster '{self.name}'",
                    args=['enable_node_pool_autorepair', pool_name]))

            # ensure auto-upgrade is DISABLED
            if "autoUpgrade" in management and management["autoUpgrade"]:
                actions.append(DAction(
                    name='disable-node-pool-autoupgrade',
                    description=f"Disable auto-upgrade for node pool '{pool_name}' in cluster '{self.name}'",
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
                        description=f"Configure auto-scaling of node pool '{pool_name}' in cluster '{self.name}'",
                        args=['configure_node_pool_autoscaling',
                              pool_name,
                              desired_pool_min_size,
                              desired_pool_max_size]))

            # infer node VM configuration
            node_config: dict = actual_pool['config'] if 'config' in actual_pool else {}

            # validate node pool service account
            desired_service_account: str = pool['service_account'] if 'service_account' in pool else 'default'
            actual_service_account: str = node_config[
                'serviceAccount'] if 'serviceAccount' in node_config else 'default'
            if desired_service_account != actual_service_account:
                raise Exception(
                    f"Node pool '{pool_name}' service account is '{actual_service_account}' instead of "
                    f"'{desired_service_account}' (updating service account is not allowed in GKE APIs unfortunately)")

            # validate node pool OAuth scopes
            desired_oauth_scopes: Sequence[str] = \
                pool['oauth_scopes'] if 'oauth_scopes' in pool else DEFAULT_OAUTH_SCOPES
            actual_oauth_scopes: Sequence[str] = node_config["oauthScopes"] if 'oauthScopes' in node_config else []
            if desired_oauth_scopes != actual_oauth_scopes:
                raise Exception(
                    f"Node pool '{pool_name}' OAuth scopes are '{actual_oauth_scopes}' instead of "
                    f"'{desired_oauth_scopes}' (updating OAuth scopes is not allowed in GKE APIs unfortunately)")

            # validate node pool preemptible usage
            desired_preemptible: bool = pool['preemptible'] if 'preemptible' in pool else True
            actual_preemptible: bool = node_config['preemptible'] if 'preemptible' in node_config else False
            if desired_preemptible != actual_preemptible:
                if desired_preemptible:
                    raise Exception(f"Node pool '{pool_name}' uses preemptibles, though it shouldn't be. "
                                    f"Updating this is not allowed in GKE APIs unfortunately.")
                else:
                    raise Exception(f"Node pool '{pool_name}' should be using preemptibles, though it isn't. "
                                    f"Updating this is not allowed in GKE APIs unfortunately.")

            # validate machine type
            desired_machine_type: str = pool[
                'machine_type'] if 'machine_type' in pool else 'n1-standard-1'
            actual_machine_type: str = node_config["machineType"] if "machineType" in node_config else 'n1-standard-1'
            if desired_machine_type != actual_machine_type:
                raise Exception(
                    f"Node pool '{pool_name}' uses '{actual_machine_type}' instead of '{desired_machine_type}'. "
                    f"Updating this is not allowed in GKE APIs unfortunately.")

            # validate machine disk type
            desired_disk_size_gb: int = pool['disk_size_gb'] if 'disk_size_gb' in pool else 20
            actual_disk_size_gb: int = node_config["diskSizeGb"] if "diskSizeGb" in node_config else 100
            if desired_disk_size_gb != actual_disk_size_gb:
                raise Exception(
                    f"Node pool '{pool_name}' allocates {actual_disk_size_gb}GB disk space instead of "
                    f"{desired_disk_size_gb}GB. Updating this is not allowed in GKE APIs unfortunately.")

            # validate network tags
            desired_tags: Sequence[str] = pool['tags'] if 'tags' in pool else []
            actual_tags: Sequence[str] = node_config["tags"] if "tags" in node_config else []
            if desired_tags != actual_tags:
                raise Exception(
                    f"Node pool '{pool_name}' network tags are '{actual_tags}' instead of '{desired_tags}'. "
                    f"Updating this is not allowed in GKE APIs unfortunately.")

            # validate GCE metadata
            desired_metadata: Mapping[str, str] = pool['metadata'] if 'metadata' in pool else {}
            actual_metadata: Mapping[str, str] = node_config["metadata"] if "metadata" in node_config else {}
            if desired_metadata != actual_metadata:
                raise Exception(
                    f"Node pool '{pool_name}' GCE metadata is '{actual_metadata}' instead of '{desired_metadata}'. "
                    f"Updating this is not allowed in GKE APIs unfortunately.")

            # validate Kubernetes labels
            desired_labels: Mapping[str, str] = pool['labels'] if 'labels' in pool else {}
            actual_labels: Mapping[str, str] = node_config["labels"] if "labels" in node_config else {}
            if desired_labels != actual_labels:
                raise Exception(
                    f"Node pool '{pool_name}' Kubernetes labels are '{actual_labels}' instead of '{desired_labels}'. "
                    f"Updating this is not allowed in GKE APIs unfortunately.")

        if not actions:
            # if no actions returned, we are VALID - create authentication for dependant resources
            self.authenticate(properties=actual_properties)

        return actions

    def define_action_args(self, action: str, argparser: argparse.ArgumentParser):
        super().define_action_args(action, argparser)
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
            argparser.add_argument('min-size', type=int, metavar='MIN-SIZE', help="minimum size of nodes in the pool")
            argparser.add_argument('max-size', type=int, metavar='MAX-SIZE', help="maximum size of nodes in the pool")

    def is_version_master_valid(self, version) -> bool:
        config = get_container().projects().zones().getServerconfig(
            projectId=self.project.project_id, zone=self.zone).execute()
        return version in config['validNodeVersions'] and self.version in config['validMasterVersions']

    def is_version_node_valid(self, version) -> bool:
        config = get_container().projects().zones().getServerconfig(
            projectId=self.project.project_id, zone=self.zone).execute()
        return version in config['validNodeVersions'] and self.version in config['validNodeVersions']

    @action
    def create_cluster(self, args):
        if args: pass
        if not self.is_version_master_valid(self.version):
            print(f"version '{self.version}' is not supported as a master version in GKE", file=sys.stderr)
            exit(1)
        elif not self.is_version_node_valid(self.version):
            print(f"version '{self.version}' is not supported as a node version in GKE", file=sys.stderr)
            exit(1)

        def build_node_pool(pool: dict):
            min_node_count = pool['min_size'] if 'min_size' in pool else 1
            return {
                "name": pool['name'],
                "version": self.version,
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
                "name": self.name,
                "description": self.description,
                "locations": [self.zone],
                "initialClusterVersion": self.version,
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
                "nodePools": [build_node_pool(pool) for pool in self.node_pools]
            },
        }

        operation = get_container().projects().zones().clusters().create(projectId=self.project.project_id,
                                                                         zone=self.zone,
                                                                         body=cluster_config).execute()
        wait_for_container_projects_zonal_operation(project_id=self.project.project_id,
                                                    zone=self.zone,
                                                    operation=operation,
                                                    timeout=60 * 15)

    @action
    def update_cluster_master_version(self, args):
        if args: pass
        if not self.is_version_master_valid(self.version):
            print(f"version '{self.version}' is not supported as a master version in GKE", file=sys.stderr)
            exit(1)
        op = get_container().projects().zones().clusters().master(projectId=self.project.project_id,
                                                                  zone=self.zone,
                                                                  clusterId=self.name,
                                                                  body={'masterVersion': self.version}).execute()
        wait_for_container_projects_zonal_operation(project_id=self.project.project_id,
                                                    zone=self.zone,
                                                    operation=op,
                                                    timeout=60 * 15)

    @action
    def disable_master_authorized_networks(self, args):
        if args: pass
        op = get_container().projects().zones().clusters().update(projectId=self.project.project_id,
                                                                  zone=self.zone,
                                                                  clusterId=self.name,
                                                                  body={
                                                                      'update': {
                                                                          'desiredMasterAuthorizedNetworksConfig': {
                                                                              'enabled': False
                                                                          }
                                                                      }
                                                                  }).execute()
        wait_for_container_projects_zonal_operation(project_id=self.project.project_id,
                                                    zone=self.zone,
                                                    operation=op,
                                                    timeout=60 * 15)

    @action
    def disable_legacy_abac(self, args):
        if args: pass
        op = get_container().projects().zones().clusters().legacyAbac(projectId=self.project.project_id,
                                                                      zone=self.zone,
                                                                      clusterId=self.name,
                                                                      body={'enabled': False}).execute()
        wait_for_container_projects_zonal_operation(project_id=self.project.project_id,
                                                    zone=self.zone,
                                                    operation=op,
                                                    timeout=60 * 15)

    @action
    def enable_monitoring_service(self, args):
        if args: pass
        op = get_container().projects().zones().clusters().monitoring(
            projectId=self.project.project_id,
            zone=self.zone,
            clusterId=self.name,
            body={'monitoringService': "monitoring.googleapis.com"}).execute()
        wait_for_container_projects_zonal_operation(project_id=self.project.project_id,
                                                    zone=self.zone,
                                                    operation=op,
                                                    timeout=60 * 15)

    @action
    def enable_logging_service(self, args):
        if args: pass
        op = get_container().projects().zones().clusters().logging(
            projectId=self.project.project_id,
            zone=self.zone,
            clusterId=self.name,
            body={'loggingService': "logging.googleapis.com"}).execute()
        wait_for_container_projects_zonal_operation(project_id=self.project.project_id,
                                                    zone=self.zone,
                                                    operation=op,
                                                    timeout=60 * 15)

    @action
    def set_addon_status(self, args):
        addon: str = args.addon
        status: str = args.status
        op = get_container().projects().zones().clusters().addons(projectId=self.project.project_id,
                                                                  zone=self.zone,
                                                                  clusterId=self.name,
                                                                  body={
                                                                      'addonsConfig': {
                                                                          addon: {'disabled': status == 'disabled'}
                                                                      }
                                                                  }).execute()
        wait_for_container_projects_zonal_operation(project_id=self.project.project_id,
                                                    zone=self.zone,
                                                    operation=op,
                                                    timeout=60 * 15)

    @action
    def create_node_pool(self, args):
        pool_name: str = args.pool
        pool: dict = next(pool for pool in self.node_pools if pool['name'] == pool_name)

        if not self.is_version_node_valid(self.version):
            print(f"version '{self.version}' is not supported as a node version in GKE", file=sys.stderr)
            exit(1)

        min_node_count = pool['min_size'] if 'min_size' in pool else 1
        pool_config = {
            "name": pool_name,
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

        operation = get_container().projects().zones().clusters().nodePools().create(
            projectId=self.project.project_id, zone=self.zone, clusterId=self.name,
            body={"nodePool": pool_config}).execute()
        wait_for_container_projects_zonal_operation(project_id=self.project.project_id,
                                                    zone=self.zone,
                                                    operation=operation,
                                                    timeout=60 * 15)

    @action
    def update_node_pool_version(self, args):
        pool_name: str = args.pool
        if not self.is_version_node_valid(self.version):
            print(f"version '{self.version}' is not supported as a node version in GKE", file=sys.stderr)
            exit(1)
        operation = get_container().projects().zones().clusters().nodePools().update(
            projectId=self.project.project_id, zone=self.zone, clusterId=self.name, nodePoolId=pool_name,
            body={"nodeVersion": self.version}).execute()
        wait_for_container_projects_zonal_operation(project_id=self.project.project_id,
                                                    zone=self.zone,
                                                    operation=operation,
                                                    timeout=60 * 15)

    @action
    def enable_node_pool_autorepair(self, args):
        pool_name: str = args.pool
        operation = get_container().projects().zones().clusters().nodePools().setManagement(
            projectId=self.project.project_id, zone=self.zone, clusterId=self.name, nodePoolId=pool_name,
            body={"management": {"autoRepair": True}}).execute()
        wait_for_container_projects_zonal_operation(project_id=self.project.project_id,
                                                    zone=self.zone,
                                                    operation=operation,
                                                    timeout=60 * 15)

    @action
    def disable_node_pool_autoupgrade(self, args):
        pool_name: str = args.pool
        operation = get_container().projects().zones().clusters().nodePools().setManagement(
            projectId=self.project.project_id, zone=self.zone, clusterId=self.name, nodePoolId=pool_name,
            body={"management": {"autoUpgrade": False}}).execute()
        wait_for_container_projects_zonal_operation(project_id=self.project.project_id,
                                                    zone=self.zone,
                                                    operation=operation,
                                                    timeout=60 * 15)

    @action
    def configure_node_pool_autoscaling(self, args):
        pool_name: str = args.pool
        min_size: int = args.min_size
        max_size: int = args.max_size
        op = get_container().projects().zones().clusters().nodePools().autoscaling(
            projectId=self.project.project_id,
            zone=self.zone,
            clusterId=self.name,
            nodePoolId=pool_name,
            body={
                'autoscaling': {
                    'enabled': True,
                    'minNodeCount': min_size,
                    'maxNodeCount': max_size
                }
            }).execute()
        wait_for_container_projects_zonal_operation(project_id=self.project.project_id,
                                                    zone=self.zone,
                                                    operation=op,
                                                    timeout=60 * 15)


def main():
    GkeCluster(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
