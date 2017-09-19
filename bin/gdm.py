import sys
import time

import os
from jinja2 import Template

from util.google import get_deployment_manager, wait_for_google_deployment_manager_operation


def collect_templates():
    imports = []
    templates_dir = '/deploy/staging/gdm/templates'
    if os.path.isdir(templates_dir):
        for entry in os.listdir(templates_dir):
            entry_path = templates_dir + '/' + entry
            if os.path.isfile(entry_path) and entry.endswith('.py'):
                imports.append({'name': entry, 'content': open(entry_path, 'r').read()})
    return imports


def build_deployment(env, deployment_name):
    return {
        'name': deployment_name,
        'description': "Auto-deployment.",
        'target': {
            'imports': collect_templates(),
            'config': {
                'content': Template(open('/deploy/staging/gdm/%s.yaml' % deployment_name, 'r').read()).render(env)
            }
        }
    }


def deployment_exists(project_id, deployment_name):
    name_filter = 'name eq ' + deployment_name
    deployments_service = get_deployment_manager().deployments()
    deployments_result = deployments_service.list(project=project_id, filter=name_filter).execute()
    return 'deployments' in deployments_result and len(deployments_result['deployments']) > 0


def execute_deployment(env, deployment_name, strategy):
    deployments_service = get_deployment_manager().deployments()
    manifests_service = get_deployment_manager().manifests()
    project_id = env['project']['projectId']
    body = build_deployment(env, deployment_name)

    # if first deployment, just create it and return
    if not deployment_exists(project_id, deployment_name):
        sys.stdout.write("Creating deployment '%s'..." % deployment_name)
        sys.stdout.flush()
        wait_for_google_deployment_manager_operation(project_id, deployments_service.insert(
            project=project_id, body=body).execute())
        return

    # otherwise, compare manifests and skip if unchanged
    deployment = deployments_service.get(project=project_id, deployment=deployment_name).execute()
    manifest_url = deployment['manifest'] if 'manifest' in deployment else ''
    if manifest_url:
        manifest = manifests_service.get(project=project_id,
                                         deployment=deployment_name,
                                         manifest=manifest_url[manifest_url.rfind('/') + 1:]).execute()
    else:
        # edge case where deployment exists, but has no manifest - when all previous runs failed
        manifest = {'config': {'content': ''}}

    # skip if there's no change, and the strategy is not configured to UPDATE ALWAYS
    if strategy != "update_always" and body['target']['config']['content'] == manifest['config']['content']:
        sys.stdout.write("Skipping deployment '%s' (no change)\n" % deployment_name)
        sys.stdout.flush()
        return

    # if strategy is to recreate the deployment, we first delete it, and then create it
    if strategy == "recreate":
        sys.stdout.write("Deleting deployment '%s'..." % deployment_name)
        sys.stdout.flush()
        wait_for_google_deployment_manager_operation(project_id,
                                                     deployments_service.delete(project=project_id,
                                                                                deployment=deployment_name,
                                                                                deletePolicy='DELETE').execute())

        sys.stdout.write("Creating deployment '%s'..." % deployment_name)
        sys.stdout.flush()
        wait_for_google_deployment_manager_operation(project_id,
                                                     deployments_service.insert(project=project_id,
                                                                                body=body).execute())

    # otherwise if strategy is to ONLY create (no updates) then just log a warning that the change IS NOT applied
    elif strategy == "create_only" and manifest['config']['content'] != '':
        sys.stdout.write("\n-------------------------------------------------------------------------------------\n")
        sys.stdout.write("SKIPPING MODIFIED CREATE-ONLY DEPLOYMENT '%s' (ALREADY EXISTS)\n" % deployment_name)
        sys.stdout.write("-------------------------------------------------------------------------------------\n\n")
        sys.stdout.flush()
        return

    else:
        sys.stdout.write("Updating deployment '%s'..." % deployment_name)
        sys.stdout.flush()
        deployment = deployment
        body['description'] = deployment['description'] if 'description' in deployment else 'Auto-generated'
        body['fingerprint'] = deployment['fingerprint']
        wait_for_google_deployment_manager_operation(project_id,
                                                     deployments_service.update(
                                                         project=project_id,
                                                         deployment=deployment_name,
                                                         body=body,
                                                         deletePolicy='DELETE',
                                                         createPolicy='CREATE_OR_ACQUIRE').execute())


def execute_gdm_configurations(env):
    if 'gdm' not in env or 'configurations' not in env['gdm']:
        print "No Google Deployment Manager configuration found in environment."
        return

    # Deployment strategy can be:
    #   - create_only
    #   - update_always
    #   - update_if_changed
    #   - recreate
    default_deployment_strategy = \
        env['gdm']['defaultStrategy'] if 'defaultStrategy' in env['gdm'] else 'update_if_changed'

    start = time.time()
    for deployment in env['gdm']['configurations']:
        name_ = deployment['name']
        strategy_ = deployment['strategy'] if 'strategy' in deployment else default_deployment_strategy
        execute_deployment(env, name_, strategy_)
    end = time.time()
    print "Executed deployments in %s seconds." % str(end - start)
