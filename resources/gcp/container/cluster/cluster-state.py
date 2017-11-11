#!/usr/bin/env python3

import json
import sys

from googleapiclient.errors import HttpError

from deployster.gcp.gke import DEFAULT_OAUTH_SCOPES
from deployster.gcp.services import get_container


class InvalidStatusError(Exception):

    def __init__(self, message, *args: object) -> None:
        super().__init__(*args)
        self._message = message

    @property
    def message(self):
        return self._message


def build_invalid_status(reason):
    return {'status': "INVALID", 'reason': reason}


def build_action(project_id, cluster_zone, cluster_name,
                 action_name, action_description, action_entrypoint=None, args=None):
    action_args = ['--project-id', project_id, '--zone', cluster_zone, '--name', cluster_name]
    if args:
        action_args.extend(args)
    return {
        'name': action_name,
        'description': action_description,
        'entrypoint': '/deployster/' + (action_entrypoint if action_entrypoint else action_name + '.py'),
        'args': action_args
    }


def get_cluster_node_pool_actions(project_id, cluster_zone, cluster_name,
                                  desired_cluster, pool_name, desired_pool):

    # TODO: some node pool changes are not supported by the API currently; support delete+create instead
    # get actual state of the node pool
    try:
        actual_pool = get_container().projects().zones().clusters().nodePools().get(projectId=project_id,
                                                                                    zone=cluster_zone,
                                                                                    clusterId=cluster_name,
                                                                                    nodePoolId=pool_name).execute()
    except HttpError as e:
        if e.resp.status == 404:
            return [build_action(project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name,
                                 action_name='create-node-pool',
                                 action_description=f"'Create missing node pool '{pool_name}'",
                                 args=['--pool', pool_name])]
        else:
            raise InvalidStatusError(str(e))

    # holder for required actions
    actions = []

    # ensure the node pool is RUNNING
    if actual_pool['status'] != "RUNNING":
        raise InvalidStatusError(f"Node pool '{pool_name}' is not running ('{actual_pool['status']}')")

    # validate node pool version
    if desired_cluster['version'] != actual_pool["version"]:
        raise InvalidStatusError(
            f"Node pool '{pool_name}' version is '{actual_pool['version']}' (should be '{desired_cluster['version']}')")

    # infer node pool management features
    management = actual_pool["management"] if "management" in actual_pool else {}

    # ensure auto-repair is ENABLED
    if "autoRepair" not in management or not management["autoRepair"]:
        raise InvalidStatusError(f"Node pool '{pool_name}' auto-repair is disabled (should be enabled)")

    # ensure auto-upgrade is DISABLED
    if "autoUpgrade" in management and management["autoUpgrade"]:
        raise InvalidStatusError(f"Node pool '{pool_name}' auto-upgrade is enabled (should be disabled)")

    # validate auto-scaling
    desired_pool_min_size = desired_pool['min_size'] if 'min_size' in desired_pool else 1
    desired_pool_max_size = desired_pool['max_size'] if 'max_size' in desired_pool else desired_pool_min_size
    actual_auto_scaling = actual_pool["autoscaling"] if "autoscaling" in actual_pool else {}
    actual_auto_scaling_enabled = "enabled" in actual_auto_scaling and actual_auto_scaling["enabled"]
    actual_auto_scaling_min_size = actual_auto_scaling["minNodeCount"] if "minNodeCount" in actual_auto_scaling else -1
    actual_auto_scaling_max_size = actual_auto_scaling["maxNodeCount"] if "maxNodeCount" in actual_auto_scaling else -1
    if not actual_auto_scaling_enabled \
            or actual_auto_scaling_min_size != desired_pool_min_size \
            or actual_auto_scaling_max_size != desired_pool_max_size:
        build_action(project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name,
                     action_name='configure-node-pool-autoscaling',
                     action_description=f"Configure auto-scaling of node pool '{pool_name}'",
                     args=['--pool', pool_name,
                           '--min-size', desired_pool_min_size,
                           '--max-size', desired_pool_max_size])

    # infer node VM configuration
    node_config = actual_pool['config'] if 'config' in actual_pool else {}
    desired_service_account = desired_pool['service_account'] if 'service_account' in desired_pool else 'default'
    actual_service_account = node_config['serviceAccount'] if 'serviceAccount' in node_config else 'default'
    desired_oauth_scopes = desired_pool['oauth_scopes'] if 'oauth_scopes' in desired_pool else DEFAULT_OAUTH_SCOPES
    actual_oauth_scopes = node_config["oauthScopes"] if 'oauthScopes' in node_config else []
    desired_preemptible = desired_pool['preemptible'] if 'preemptible' in desired_pool else True
    actual_preemptible = node_config['preemptible'] if 'preemptible' in node_config else False
    desired_machine_type = desired_pool['machine_type'] if 'machine_type' in desired_pool else 'n1-standard-1'
    actual_machine_type = node_config["machineType"] if "machineType" in node_config else 'n1-standard-1'
    desired_disk_size_gb = desired_pool['disk_size_gb'] if 'disk_size_gb' in desired_pool else 20
    actual_disk_size_gb = node_config["diskSizeGb"] if "diskSizeGb" in node_config else 100
    desired_tags = desired_pool['tags'] if 'tags' in desired_pool else []
    actual_tags = node_config["tags"] if "tags" in node_config else []
    desired_metadata = desired_pool['metadata'] if 'metadata' in desired_pool else {}
    actual_metadata = node_config["metadata"] if "metadata" in node_config else {}
    desired_labels = desired_pool['labels'] if 'labels' in desired_pool else {}
    actual_labels = node_config["labels"] if "labels" in node_config else {}

    # validate node pool service account
    if desired_service_account != actual_service_account:
        raise InvalidStatusError(
            f"Node pool '{pool_name}' service account is '{actual_service_account}' "
            f"(should be '{desired_service_account}')")

    # validate node pool OAuth scopes
    if desired_oauth_scopes != actual_oauth_scopes:
        raise InvalidStatusError(
            f"Node pool '{pool_name}' OAuth scopes are '{actual_oauth_scopes}' (should be '{desired_oauth_scopes}')")

    # validate node pool preemptible usage
    if desired_preemptible != actual_preemptible:
        if desired_preemptible:
            raise InvalidStatusError(f"Node pool '{pool_name}' uses preemptibles (it shouldn't be)")
        else:
            raise InvalidStatusError(f"Node pool '{pool_name}' should be using preemptibles (it isn't)")

    # validate machine type
    if desired_machine_type != actual_machine_type:
        raise InvalidStatusError(
            f"Node pool '{pool_name}' uses '{actual_machine_type}' (should be using '{desired_machine_type}')")

    # validate machine disk type
    if desired_disk_size_gb != actual_disk_size_gb:
        raise InvalidStatusError(
            f"Node pool '{pool_name}' allocates {actual_disk_size_gb}GB disk space "
            f"(should be allocating {desired_disk_size_gb}GB)")

    # validate network tags
    if desired_tags != actual_tags:
        raise InvalidStatusError(
            f"Node pool '{pool_name}' network tags are '{actual_tags}' (should be '{desired_tags}')")

    # validate GCE metadata
    if desired_metadata != actual_metadata:
        raise InvalidStatusError(
            f"Node pool '{pool_name}' GCE metadata is '{actual_metadata}' (should be '{desired_metadata}')")

    # validate Kubernetes labels
    if desired_labels != actual_labels:
        raise InvalidStatusError(
            f"Node pool '{pool_name}' Kubernetes labels are '{actual_labels}' (should be '{desired_labels}')")

    return actions


def get_cluster_state(desired_cluster, actual_cluster):
    status = 'VALID'
    actions = []

    project_id = desired_cluster['project']['project_id']
    cluster_zone = desired_cluster['zone']
    cluster_name = desired_cluster['name']

    # validate cluster is RUNNING
    if actual_cluster['status'] != "RUNNING":
        raise InvalidStatusError(f"Cluster is not running ('{actual_cluster['status']}')")

    # validate cluster primary zone & locations
    actual_cluster_zone = actual_cluster['zone']
    actual_cluster_locations = actual_cluster['locations']
    if cluster_zone != actual_cluster_zone:
        raise InvalidStatusError(f"Cluster primary zone is '{actual_cluster_zone}' (should be '{cluster_zone}')")
    elif [cluster_zone] != actual_cluster_locations:
        raise InvalidStatusError(f"Cluster locations are '{actual_cluster_locations}' (should be '{[cluster_zone]}')")

    # validate cluster master version & cluster node pools version
    desired_version = desired_cluster['version']
    actual_cluster_master_version = actual_cluster["currentMasterVersion"]
    actual_cluster_node_version = actual_cluster["currentNodeVersion"]
    if desired_version != actual_cluster_master_version:
        raise InvalidStatusError(
            f"Cluster master version is '{actual_cluster_master_version}' (should be '{desired_version}')")
    elif desired_version != actual_cluster_node_version:
        raise InvalidStatusError(
            f"Cluster node version is '{actual_cluster_node_version}' (should be '{desired_version}')")

    # ensure master authorized networks is disabled
    if 'masterAuthorizedNetworksConfig' in actual_cluster:
        if 'enabled' in actual_cluster['masterAuthorizedNetworksConfig']:
            if actual_cluster['masterAuthorizedNetworksConfig']['enabled']:
                status = "STALE"
                actions.append(build_action(project_id, cluster_zone, cluster_name,
                                            'disable-master-authorized-networks',
                                            'Disable master authorized networks'))

    # ensure that legacy ABAC is disabled
    if 'legacyAbac' in actual_cluster:
        if 'enabled' in actual_cluster['legacyAbac']:
            if actual_cluster['legacyAbac']['enabled']:
                status = "STALE"
                actions.append(build_action(project_id, cluster_zone, cluster_name,
                                            'disable-legacy-abac', 'Disable legacy ABAC authorization'))

    # ensure monitoring service is set to GKE's monitoring service
    if "monitoringService" not in actual_cluster or actual_cluster["monitoringService"] != "monitoring.googleapis.com":
        status = "STALE"
        actions.append(build_action(project_id, cluster_zone, cluster_name,
                                    'enable-monitoring-service', 'Enable monitoring service'))

    # ensure logging service is set to GKE's logging service
    if "loggingService" not in actual_cluster or actual_cluster["loggingService"] != "logging.googleapis.com":
        status = "STALE"
        actions.append(
            build_action(project_id, cluster_zone, cluster_name, 'enable-logging-service', 'Enable logging service'))

    # infer actual addons status
    actual_addons_config = actual_cluster["addonsConfig"] if "addonsConfig" in actual_cluster else {}
    http_lb_addon = actual_addons_config["httpLoadBalancing"] if "httpLoadBalancing" in actual_addons_config else {}
    k8s_dashboard_addon = \
        actual_addons_config["kubernetesDashboard"] if "kubernetesDashboard" in actual_addons_config else {}
    horiz_pod_auto_scaling_addon = \
        actual_addons_config["horizontalPodAutoscaling"] if "horizontalPodAutoscaling" in actual_addons_config else {}

    # ensure HTTP load-balancing addon is ENABLED
    if 'disabled' in http_lb_addon and http_lb_addon["disabled"]:
        status = "STALE"
        actions.append(build_action(project_id, cluster_zone, cluster_name,
                                    'set-addon-status', 'Enable HTTP load-balancing addon',
                                    args=['--addon', 'httpLoadBalancing', '--status', 'enabled']))

    # ensure Kubernetes Dashboard addon is DISABLED
    if "disabled" in k8s_dashboard_addon and not k8s_dashboard_addon["disabled"]:
        status = "STALE"
        actions.append(build_action(project_id, cluster_zone, cluster_name,
                                    'set-addon-status', 'Disable legacy Kubernetes Dashboard addon',
                                    args=['--addon', 'kubernetesDashboard', '--status', 'disabled']))

    # ensure Horizontal Pod Auto-scaling addon is ENABLED
    if "disabled" in horiz_pod_auto_scaling_addon and horiz_pod_auto_scaling_addon["disabled"]:
        status = "STALE"
        actions.append(build_action(project_id, cluster_zone, cluster_name,
                                    'set-addon-status', 'Enable horizontal Pod auto-scaling addon',
                                    args=['--addon', 'horizontalPodAutoscaling', '--status', 'enabled']))

    # ensure alpha features are DISABLED
    if 'enableKubernetesAlpha' in actual_cluster and actual_cluster["enableKubernetesAlpha"]:
        raise InvalidStatusError(f"Cluster alpha features are enabled (should be disabled)")

    # validate node pools state
    for pool in desired_cluster['node_pools']:
        pool_actions = get_cluster_node_pool_actions(
            project_id=project_id, cluster_zone=cluster_zone, cluster_name=cluster_name,
            desired_cluster=desired_cluster, pool_name=pool['name'], desired_pool=pool)
        if pool_actions:
            status = "STALE"
            actions.extend(pool_actions)

    # return a summary of the status & required actions
    return {
        'status': status,
        'actions': actions,
        'properties': actual_cluster
    }


def main():
    params = json.loads(sys.stdin.read())
    clusters_service = get_container().projects().zones().clusters()
    try:
        properties = params['properties']
        cluster = clusters_service.get(projectId=properties['project']['project_id'],
                                       zone=properties['zone'],
                                       clusterId=properties['name']).execute()
        state = get_cluster_state(desired_cluster=properties, actual_cluster=cluster)

    except InvalidStatusError as e:
        state = {
            'status': 'INVALID',
            'reason': e.message
        }

    except HttpError as e:
        if e.resp.status == 404:
            state = {
                'status': 'MISSING',
                'actions': [{
                    'name': 'create-cluster',
                    'description': f"Create GKE cluster",
                    'entrypoint': '/deployster/create-cluster.py'
                }]
            }
        else:
            state = {
                'status': 'INVALID',
                'reason': str(e)
            }

    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
