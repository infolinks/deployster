#!/usr/bin/env python3

import json
import sys

from deployster.gcp.projects import find_project, ProjectNotFoundError, TooManyProjectsMatchError
from deployster.gcp.services import get_billing, get_service_management


# TODO: create action to allow GCR access to new project's default service account
# subprocess.check_call(
#     "gcloud projects add-iam-policy-binding %s " % gcr_project_id +
#     ("--member='serviceAccount:%s-compute@developer.gserviceaccount.com' " % project['projectNumber']) +
#     "--role='roles/storage.objectViewer'",
#     shell=True)


def create_project_action(project_id, organization_id=None):
    args = [
        '--project-id', project_id,
        '--name', project_id
    ]
    if organization_id:
        args.extend(['--organization-id', organization_id])

    return {
        'name': 'create-project',
        'description': f"Create project {project_id}",
        'entrypoint': '/deployster/create-project.py',
        'args': args
    }


def set_organization_action(project_id, organization_id):
    return {
        'name': 'set-organization',
        'description': f"Attach project '{project_id}' to organization '{organization_id}'",
        'entrypoint': '/deployster/set-organization.py',
        'args': [
            '--project-id', project_id,
            '--organization-id', organization_id
        ]
    }


def clear_organization_action(project_id):
    return {
        'name': 'clear-organization',
        'description': f"Detach project '{project_id}' from parent",
        'entrypoint': '/deployster/clear-organization.py',
        'args': ['--project-id', project_id]
    }


def set_billing_account_action(project_id, billing_account_id):
    return {
        'name': 'set-billing-account',
        'description': f"Update billing account of project '{project_id}' to '{billing_account_id}'",
        'entrypoint': '/deployster/set-billing-account.py',
        'args': [
            '--project-id', project_id,
            '--billing-account-id', billing_account_id
        ]
    }


def clear_billing_account_action(project_id):
    return {
        'name': 'clear-billing-account',
        'description': f"Detach project '{project_id}' from its billing account",
        'entrypoint': '/deployster/clear-billing-account.py',
        'args': ['--project-id', project_id]
    }


def enable_api(project_id, api_name):
    return {
        'name': 'enable-service-api',
        'description': f"Enable API '{api_name}' for project '{project_id}'",
        'entrypoint': '/deployster/enable-service-api.py',
        'args': [
            '--project-id', project_id,
            '--api', api_name
        ]
    }


def disable_api(project_id, api_name):
    return {
        'name': 'disable-service-api',
        'description': f"Disable API '{api_name}' for project '{project_id}'",
        'entrypoint': '/deployster/disable-service-api.py',
        'args': [
            '--project-id', project_id,
            '--api', api_name
        ]
    }


def handle_project_exists(project_id, desired_properties, project):
    desired_parent_id = desired_properties['organization_id'] if 'organization_id' in desired_properties else None
    desired_billing_account_id = \
        desired_properties['billing_account_id'] if 'billing_account_id' in desired_properties else None
    desired_enabled_api_names = desired_properties['apis']['enabled'] \
        if 'apis' in desired_properties and 'enabled' in desired_properties['apis'] else []
    desired_disabled_api_names = desired_properties['apis']['disabled'] \
        if 'apis' in desired_properties and 'disabled' in desired_properties['apis'] else []

    status = 'VALID'
    actions = []
    actual_parent = project['parent'] if 'parent' in project else {}
    actual_parent_id = int(actual_parent['id']) if 'id' in actual_parent else None
    actual_billing = get_billing().projects().getBillingInfo(name=f"projects/{project_id}").execute()
    actual_billing_account_id = actual_billing['billingAccountName'][len('billingAccounts/'):] \
        if 'billingAccountName' in actual_billing else None

    # compare project organization
    if desired_parent_id and desired_parent_id != actual_parent_id:
        status = 'STALE'
        actions.append(set_organization_action(project_id=project_id, organization_id=desired_parent_id))
    elif not desired_parent_id and actual_parent_id:
        status = 'STALE'
        actions.append(clear_organization_action(project_id=project_id))

    # compare project billing account
    if desired_billing_account_id and desired_billing_account_id != actual_billing_account_id:
        status = 'STALE'
        actions.append(set_billing_account_action(project_id=project_id, billing_account_id=desired_billing_account_id))
    elif not desired_billing_account_id and actual_billing_account_id:
        status = 'STALE'
        actions.append(clear_billing_account_action(project_id=project_id))

    # compare project APIs
    actual_enabled_apis = get_service_management().services().list(consumerId=f'project:{project_id}').execute()
    apis = actual_enabled_apis['services'] if 'services' in actual_enabled_apis else []
    actual_enabled_api_names = [api['serviceName'] for api in apis]
    for api_name in desired_enabled_api_names:
        if api_name not in actual_enabled_api_names:
            status = 'STALE'
            actions.append(enable_api(project_id=project_id, api_name=api_name))
    for api_name in desired_disabled_api_names:
        if api_name in actual_enabled_api_names:
            status = 'STALE'
            actions.append(disable_api(project_id=project_id, api_name=api_name))

    # return status, state, and possibly actions
    return {
        'status': status,
        'actions': actions,
        'properties': {
            'project_id': project_id,
            'project_number': project['projectNumber'],
            'organization_id': actual_parent_id,
            'billing_account_id': actual_billing_account_id,
            'apis': {
                'enabled': actual_enabled_api_names
            }
        }
    }


def main():
    params = json.loads(sys.stdin.read())
    properties = params['properties']
    project_id = properties['project_id']
    try:
        state = handle_project_exists(project_id=project_id,
                                      desired_properties=properties,
                                      project=find_project(project_id=project_id))

    except TooManyProjectsMatchError:
        state = {
            'status': "INVALID",
            'reason': f"more than one project is named '{properties['project_id']}'"
        }

    except ProjectNotFoundError:
        organization_id = properties['organization_id'] if 'organization_id' in properties else None
        actions = [create_project_action(project_id=project_id, organization_id=organization_id)]
        if 'billing_account_id' in params:
            billing_account_id = params['billing_account_id']
            actions.append(set_billing_account_action(project_id=project_id, billing_account_id=billing_account_id))
        for api_name in params['properties']['apis']['disabled']:
            actions.append(disable_api(project_id=project_id, api_name=api_name))
        for api_name in params['properties']['apis']['enabled']:
            actions.append(enable_api(project_id=project_id, api_name=api_name))
        state = {
            'status': "MISSING",
            'actions': actions
        }

    print(json.dumps(state))


if __name__ == "__main__":
    main()
