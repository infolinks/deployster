#!/usr/bin/env python3

import json
import sys
from typing import Sequence, MutableSequence, Mapping

from googleapiclient.errors import HttpError

from deployster.gcp.gke import DEFAULT_OAUTH_SCOPES
from deployster.gcp.services import get_container


class ClusterNotFoundError(Exception):

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class NodePoolNotFoundError(Exception):

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


def find_cluster(project_id: str, cluster_zone: str, cluster_name: str) -> dict:
    clusters_service = get_container().projects().zones().clusters()
    try:
        return clusters_service.get(projectId=project_id, zone=cluster_zone, clusterId=cluster_name).execute()
    except HttpError as e:
        if e.resp.status == 404:
            raise ClusterNotFoundError() from e
        else:
            raise


def find_node_pool(project_id: str, cluster_zone: str, cluster_name: str, pool_name: str) -> dict:
    try:
        return get_container().projects().zones().clusters().nodePools().get(projectId=project_id,
                                                                             zone=cluster_zone,
                                                                             clusterId=cluster_name,
                                                                             nodePoolId=pool_name).execute()
    except HttpError as e:
        if e.resp.status == 404:
            raise NodePoolNotFoundError() from e
        else:
            raise


class InvalidStatusError(Exception):

    def __init__(self, message, *args: object) -> None:
        super().__init__(*args)
        self._message = message

    @property
    def message(self):
        return self._message


def build_action(name: str, description: str = None, entrypoint: str = None, args: Sequence[str] = None) -> dict:
    return {
        'name': name,
        'description': description if description else name.capitalize().replace('-', ' '),
        'entrypoint': '/deployster/' + (entrypoint if entrypoint else name + '.py'),
        'args': args if args else []
    }


def build_cluster_action(project_id: str, cluster_zone: str, cluster_name: str,
                         name: str, description: str = None,
                         entrypoint: str = None, args: Sequence[str] = None) -> dict:
    full_args: MutableSequence[str] = ['--project-id', project_id, '--zone', cluster_zone, '--name', cluster_name]
    if args:
        full_args.extend(args)
    return build_action(name=name, description=description, entrypoint=entrypoint, args=full_args)


def get_cluster_node_pool_actions(project_id: str, cluster_zone: str, cluster_name: str,
                                  desired_cluster: dict, pool_name: str, desired_pool: dict) -> Sequence[dict]:
    # TODO: some node pool changes are not supported by the API currently; support delete+create instead
    try:
        actual_pool: dict = find_node_pool(project_id=project_id,
                                           cluster_zone=cluster_zone,
                                           cluster_name=cluster_name,
                                           pool_name=pool_name)
    except NodePoolNotFoundError:
        return [build_cluster_action(project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name,
                                     name='create-node-pool',
                                     description=f"'Create node pool '{pool_name}' in cluster '{cluster_name}'",
                                     args=['--pool', pool_name])]

    # holder for required actions
    actions: MutableSequence[dict] = []

    # ensure the node pool is RUNNING
    if actual_pool['status'] != "RUNNING":
        raise InvalidStatusError(f"Node pool '{pool_name}' exists, but not running ('{actual_pool['status']}')")

    # validate node pool version
    if desired_cluster['version'] != actual_pool["version"]:
        actions.append(build_cluster_action(
            project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name,
            name='update-node-pool-version',
            description=f"Update version of node pool '{pool_name}' in cluster '{cluster_name}'",
            args=['--pool', pool_name, '--version', desired_cluster['version']]))

    # infer node pool management features
    management: dict = actual_pool["management"] if "management" in actual_pool else {}

    # ensure auto-repair is ENABLED
    if "autoRepair" not in management or not management["autoRepair"]:
        actions.append(build_cluster_action(
            project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name,
            name='enable-node-pool-autorepair',
            description=f"Enable auto-repair for node pool '{pool_name}' in cluster '{cluster_name}'",
            args=['--pool', pool_name]))

    # ensure auto-upgrade is DISABLED
    if "autoUpgrade" in management and management["autoUpgrade"]:
        actions.append(build_cluster_action(
            project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name,
            name='disable-node-pool-autoupgrade',
            description=f"Disable auto-upgrade for node pool '{pool_name}' in cluster '{cluster_name}'",
            args=['--pool', pool_name]))

    # validate auto-scaling
    desired_pool_min_size: int = desired_pool['min_size'] if 'min_size' in desired_pool else 1
    desired_pool_max_size: int = desired_pool['max_size'] if 'max_size' in desired_pool else desired_pool_min_size
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
            build_cluster_action(
                project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name,
                name='configure-node-pool-autoscaling',
                description=f"Configure auto-scaling of node pool '{pool_name}' in cluster '{cluster_name}'",
                args=['--pool', pool_name,
                      '--min-size', desired_pool_min_size,
                      '--max-size', desired_pool_max_size]))

    # infer node VM configuration
    node_config: dict = actual_pool['config'] if 'config' in actual_pool else {}

    # validate node pool service account
    desired_service_account: str = desired_pool['service_account'] if 'service_account' in desired_pool else 'default'
    actual_service_account: str = node_config['serviceAccount'] if 'serviceAccount' in node_config else 'default'
    if desired_service_account != actual_service_account:
        raise InvalidStatusError(
            f"Node pool '{pool_name}' service account is '{actual_service_account}' instead of "
            f"'{desired_service_account}' (updating service account is not allowed in GKE APIs unfortunately)")

    # validate node pool OAuth scopes
    desired_oauth_scopes: Sequence[str] = \
        desired_pool['oauth_scopes'] if 'oauth_scopes' in desired_pool else DEFAULT_OAUTH_SCOPES
    actual_oauth_scopes: Sequence[str] = node_config["oauthScopes"] if 'oauthScopes' in node_config else []
    if desired_oauth_scopes != actual_oauth_scopes:
        raise InvalidStatusError(
            f"Node pool '{pool_name}' OAuth scopes are '{actual_oauth_scopes}' instead of '{desired_oauth_scopes}' "
            f"(updating OAuth scopes is not allowed in GKE APIs unfortunately)")

    # validate node pool preemptible usage
    desired_preemptible: bool = desired_pool['preemptible'] if 'preemptible' in desired_pool else True
    actual_preemptible: bool = node_config['preemptible'] if 'preemptible' in node_config else False
    if desired_preemptible != actual_preemptible:
        if desired_preemptible:
            raise InvalidStatusError(f"Node pool '{pool_name}' uses preemptibles, though it shouldn't be. "
                                     f"Updating this is not allowed in GKE APIs unfortunately.")
        else:
            raise InvalidStatusError(f"Node pool '{pool_name}' should be using preemptibles, though it isn't. "
                                     f"Updating this is not allowed in GKE APIs unfortunately.")

    # validate machine type
    desired_machine_type: str = desired_pool['machine_type'] if 'machine_type' in desired_pool else 'n1-standard-1'
    actual_machine_type: str = node_config["machineType"] if "machineType" in node_config else 'n1-standard-1'
    if desired_machine_type != actual_machine_type:
        raise InvalidStatusError(
            f"Node pool '{pool_name}' uses '{actual_machine_type}' instead of '{desired_machine_type}'. "
            f"Updating this is not allowed in GKE APIs unfortunately.")

    # validate machine disk type
    desired_disk_size_gb: int = desired_pool['disk_size_gb'] if 'disk_size_gb' in desired_pool else 20
    actual_disk_size_gb: int = node_config["diskSizeGb"] if "diskSizeGb" in node_config else 100
    if desired_disk_size_gb != actual_disk_size_gb:
        raise InvalidStatusError(
            f"Node pool '{pool_name}' allocates {actual_disk_size_gb}GB disk space instead of {desired_disk_size_gb}GB."
            f"Updating this is not allowed in GKE APIs unfortunately.")

    # validate network tags
    desired_tags: Sequence[str] = desired_pool['tags'] if 'tags' in desired_pool else []
    actual_tags: Sequence[str] = node_config["tags"] if "tags" in node_config else []
    if desired_tags != actual_tags:
        raise InvalidStatusError(
            f"Node pool '{pool_name}' network tags are '{actual_tags}' instead of '{desired_tags}'. "
            f"Updating this is not allowed in GKE APIs unfortunately.")

    # validate GCE metadata
    desired_metadata: Mapping[str, str] = desired_pool['metadata'] if 'metadata' in desired_pool else {}
    actual_metadata: Mapping[str, str] = node_config["metadata"] if "metadata" in node_config else {}
    if desired_metadata != actual_metadata:
        raise InvalidStatusError(
            f"Node pool '{pool_name}' GCE metadata is '{actual_metadata}' instead of '{desired_metadata}'. "
            f"Updating this is not allowed in GKE APIs unfortunately.")

    # validate Kubernetes labels
    desired_labels: Mapping[str, str] = desired_pool['labels'] if 'labels' in desired_pool else {}
    actual_labels: Mapping[str, str] = node_config["labels"] if "labels" in node_config else {}
    if desired_labels != actual_labels:
        raise InvalidStatusError(
            f"Node pool '{pool_name}' Kubernetes labels are '{actual_labels}' instead of '{desired_labels}'. "
            f"Updating this is not allowed in GKE APIs unfortunately.")

    return actions


def get_cluster_state(project_id: str, cluster_zone: str, cluster_name: str,
                      desired_cluster: dict, actual_cluster: dict):
    actions: MutableSequence[dict] = []

    # validate cluster is RUNNING
    if actual_cluster['status'] != "RUNNING":
        raise InvalidStatusError(f"Cluster exists, but not running ('{actual_cluster['status']}')")

    # validate cluster primary zone & locations
    actual_cluster_zone: str = actual_cluster['zone']
    actual_cluster_locations: Sequence[str] = actual_cluster['locations']
    if cluster_zone != actual_cluster_zone:
        raise InvalidStatusError(
            f"Cluster primary zone is '{actual_cluster_zone}' instead of '{cluster_zone}'. "
            f"Updating this is not allowed in GKE APIs unfortunately.")
    elif [cluster_zone] != actual_cluster_locations:
        raise InvalidStatusError(
            f"Cluster locations are '{actual_cluster_locations}' instead of '{[cluster_zone]}'. "
            f"Updating this is not allowed in GKE APIs unfortunately.")

    # validate cluster master version & cluster node pools version
    desired_version: str = desired_cluster['version']
    actual_cluster_master_version: str = actual_cluster["currentMasterVersion"]
    actual_cluster_node_version: str = actual_cluster["currentNodeVersion"]
    if desired_version != actual_cluster_master_version:
        actions.append(
            build_cluster_action(
                project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name,
                name='update-cluster-master-version',
                description=f"Update master version for cluster '{cluster_name}'",
                args=['--version', desired_version]))
    if desired_version != actual_cluster_node_version:
        raise InvalidStatusError(
            f"Cluster node version is '{actual_cluster_node_version}' instead of '{desired_version}'. "
            f"Updating this is not allowed in GKE APIs unfortunately.")

    # ensure master authorized networks is disabled
    if 'masterAuthorizedNetworksConfig' in actual_cluster:
        if 'enabled' in actual_cluster['masterAuthorizedNetworksConfig']:
            if actual_cluster['masterAuthorizedNetworksConfig']['enabled']:
                actions.append(
                    build_cluster_action(
                        project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name,
                        name='disable-master-authorized-networks',
                        description=f"Disable master authorized networks for cluster '{cluster_name}'"))

    # ensure that legacy ABAC is disabled
    if 'legacyAbac' in actual_cluster:
        if 'enabled' in actual_cluster['legacyAbac']:
            if actual_cluster['legacyAbac']['enabled']:
                actions.append(
                    build_cluster_action(
                        project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name,
                        name='disable-legacy-abac',
                        description=f"Disable legacy ABAC for cluster '{cluster_name}'"))

    # ensure monitoring service is set to GKE's monitoring service
    if "monitoringService" not in actual_cluster or actual_cluster["monitoringService"] != "monitoring.googleapis.com":
        actions.append(
            build_cluster_action(
                project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name,
                name='enable-monitoring-service',
                description=f"Enable GCP monitoring for cluster '{cluster_name}'"))

    # ensure logging service is set to GKE's logging service
    if "loggingService" not in actual_cluster or actual_cluster["loggingService"] != "logging.googleapis.com":
        actions.append(
            build_cluster_action(
                project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name,
                name='enable-logging-service',
                description=f"Enable GCP logging for cluster '{cluster_name}'"))

    # infer actual addons status
    actual_addons: dict = actual_cluster["addonsConfig"] if "addonsConfig" in actual_cluster else {}

    # ensure HTTP load-balancing addon is ENABLED
    http_lb_addon: dict = actual_addons["httpLoadBalancing"] if "httpLoadBalancing" in actual_addons else {}
    if 'disabled' in http_lb_addon and http_lb_addon["disabled"]:
        actions.append(
            build_cluster_action(
                project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name,
                name='set-addon-status',
                description=f"Enable HTTP load-balancing addon for cluster '{cluster_name}'",
                args=['--addon', 'httpLoadBalancing', '--status', 'enabled']))

    # ensure Kubernetes Dashboard addon is DISABLED
    k8s_dashboard_addon = actual_addons["kubernetesDashboard"] if "kubernetesDashboard" in actual_addons else {}
    if "disabled" in k8s_dashboard_addon and not k8s_dashboard_addon["disabled"]:
        actions.append(
            build_cluster_action(
                project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name,
                name='set-addon-status',
                description=f"Disable legacy Kubernetes Dashboard addon for cluster '{cluster_name}'",
                args=['--addon', 'kubernetesDashboard', '--status', 'disabled']))

    # ensure Horizontal Pod Auto-scaling addon is ENABLED
    horiz_pod_auto_scaling_addon = \
        actual_addons["horizontalPodAutoscaling"] if "horizontalPodAutoscaling" in actual_addons else {}
    if "disabled" in horiz_pod_auto_scaling_addon and horiz_pod_auto_scaling_addon["disabled"]:
        actions.append(
            build_cluster_action(
                project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name,
                name='set-addon-status',
                description=f"Enable horizontal Pod auto-scaling addon for cluster '{cluster_name}'",
                args=['--addon', 'horizontalPodAutoscaling', '--status', 'enabled']))

    # ensure alpha features are DISABLED
    if 'enableKubernetesAlpha' in actual_cluster and actual_cluster["enableKubernetesAlpha"]:
        raise InvalidStatusError(f"Cluster alpha features are enabled instead of disabled. "
                                 f"Updating this is not allowed in GKE APIs unfortunately.")

    # validate node pools state
    for pool in desired_cluster['node_pools']:
        actions.extend(
            get_cluster_node_pool_actions(project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name,
                                          desired_cluster=desired_cluster, pool_name=pool['name'], desired_pool=pool))

    # return a summary of the status & required actions
    if len(actions) > 0:
        return {'status': 'STALE', 'actions': actions}
    else:
        return {'status': 'VALID', 'properties': actual_cluster}


def main():
    stdin: dict = json.loads(sys.stdin.read())
    cfg: dict = stdin['config']
    dependencies: dict = stdin['dependencies']

    project_id = dependencies['project']['config']['project_id']
    cluster_zone = cfg['zone']
    cluster_name = cfg['name']

    try:
        cluster = find_cluster(project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name)
        print(json.dumps(get_cluster_state(project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name,
                                           desired_cluster=cfg, actual_cluster=cluster),
                         indent=2))

    except InvalidStatusError as e:
        print(e.message, file=sys.stderr)
        exit(1)

    except ClusterNotFoundError:
        print(json.dumps({
            'status': 'MISSING',
            'actions': [build_action(name='create-cluster', description=f"Create GKE cluster '{cluster_name}'")]
        }, indent=2))


if __name__ == "__main__":
    main()
