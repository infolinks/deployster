#!/usr/bin/env python3

import json
import sys
from typing import Sequence, MutableSequence

from deployster.gcp.services import get_billing, get_service_management, get_resource_manager


# TODO: create action to allow GCR access to new project's default service account
# subprocess.check_call(
#     "gcloud projects add-iam-policy-binding %s " % gcr_project_id +
#     ("--member='serviceAccount:%s-compute@developer.gserviceaccount.com' " % project['projectNumber']) +
#     "--role='roles/storage.objectViewer'",
#     shell=True)


class ProjectNotFoundError(Exception):

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class TooManyProjectsMatchError(Exception):

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


def find_project(project_id: str) -> dict:
    result: dict = get_resource_manager().projects().list(filter="name:" + project_id).execute()
    if 'projects' not in result:
        raise ProjectNotFoundError(project_id)

    projects: Sequence[dict] = result['projects']
    if len(projects) == 0:
        raise ProjectNotFoundError(project_id)
    elif len(projects) > 1:
        raise TooManyProjectsMatchError(project_id)
    else:
        return projects[0]


def get_project_enabled_apis(project_id: str) -> Sequence[str]:
    result: dict = get_service_management().services().list(consumerId=f'project:{project_id}').execute()
    apis: Sequence[dict] = result['services'] if 'services' in result else []
    return [api['serviceName'] for api in apis]


def create_project_action(project_id: str, organization_id: int = None) -> dict:
    args: MutableSequence[str] = [
        '--project-id', project_id,
        '--project-name', project_id
    ]
    if organization_id:
        args.extend(['--organization-id', str(organization_id)])
    return {
        'name': 'create-project',
        'description': f"Create project '{project_id}'",
        'entrypoint': '/deployster/create-project.py',
        'args': args
    }


def set_organization_action(project_id: str, organization_id: int = None) -> dict:
    if organization_id:
        return {
            'name': 'set-organization',
            'description': f"Attach project '{project_id}' to organization '{organization_id}'",
            'entrypoint': '/deployster/set-organization.py',
            'args': [
                '--project-id', project_id,
                '--organization-id', str(organization_id)
            ]
        }
    else:
        return {
            'name': 'clear-organization',
            'description': f"Detach project '{project_id}' from its organization",
            'entrypoint': '/deployster/set-organization.py',
            'args': ['--project-id', project_id]
        }


def set_billing_account_action(project_id: str, billing_account_id: str = None) -> dict:
    if billing_account_id:
        return {
            'name': 'set-billing-account',
            'description': f"Update billing account of project '{project_id}' to '{billing_account_id}'",
            'entrypoint': '/deployster/set-billing-account.py',
            'args': [
                '--project-id', project_id,
                '--billing-account-id', billing_account_id
            ]
        }
    else:
        return {
            'name': 'clear-billing-account',
            'description': f"Detach project '{project_id}' from its billing account",
            'entrypoint': '/deployster/set-billing-account.py',
            'args': ['--project-id', project_id]
        }


def enable_api(project_id: str, api_name: str) -> dict:
    return {
        'name': 'enable-service-api',
        'description': f"Enable API '{api_name}' for project '{project_id}'",
        'entrypoint': '/deployster/enable-service-api.py',
        'args': [
            '--project-id', project_id,
            '--api', api_name
        ]
    }


def disable_api(project_id: str, api_name: str) -> dict:
    return {
        'name': 'disable-service-api',
        'description': f"Disable API '{api_name}' for project '{project_id}'",
        'entrypoint': '/deployster/disable-service-api.py',
        'args': [
            '--project-id', project_id,
            '--api', api_name
        ]
    }


def handle_project_exists(project_id: str,
                          actual_project: dict,
                          desired_organization_id: int = None,
                          desired_billing_account_id: str = None,
                          desired_enabled_apis: Sequence[str] = None,
                          desired_disabled_apis: Sequence[str] = None) -> dict:
    actions: MutableSequence[dict] = []
    actual_parent: dict = actual_project['parent'] if 'parent' in actual_project else {}
    actual_parent_id: int = int(actual_parent['id']) if 'id' in actual_parent else None
    actual_billing: dict = get_billing().projects().getBillingInfo(name=f"projects/{project_id}").execute()
    actual_billing_account_id: str = actual_billing['billingAccountName'][len('billingAccounts/'):] \
        if 'billingAccountName' in actual_billing else None

    # update project organization if necessary
    if desired_organization_id != actual_parent_id:
        actions.append(set_organization_action(project_id=project_id, organization_id=desired_organization_id))

    # update project billing account if necessary
    if desired_billing_account_id != actual_billing_account_id:
        actions.append(set_billing_account_action(project_id=project_id, billing_account_id=desired_billing_account_id))

    # fetch currently enabled project APIs
    actual_enabled_api_names: Sequence[str] = get_project_enabled_apis(project_id=project_id)

    # enable APIs that user desires to be enabled, if not already enabled
    apis_to_enable: Sequence[str] = \
        [api_name for api_name in desired_enabled_apis if api_name not in actual_enabled_api_names]
    if apis_to_enable:
        for api_name in apis_to_enable:
            actions.append(enable_api(project_id=project_id, api_name=api_name))

    # disable APIs that user desires to be disable, if currently enabled
    apis_to_disable: Sequence[str] = \
        [api_name for api_name in desired_disabled_apis if api_name in actual_enabled_api_names]
    if apis_to_disable:
        for api_name in apis_to_disable:
            actions.append(disable_api(project_id=project_id, api_name=api_name))

    # return status, state, and possibly actions
    if len(actions) > 0:
        return {'status': 'STALE', 'actions': actions}
    else:
        return {'status': 'VALID', 'properties': actual_project}


def create_missing_project_state(project_id: str,
                                 organization_id: int = None,
                                 billing_account_id: str = None,
                                 enabled_apis: Sequence[str] = None,
                                 disabled_apis: Sequence[str] = None) -> dict:
    actions: MutableSequence[dict] = [create_project_action(project_id=project_id, organization_id=organization_id)]
    if billing_account_id:
        actions.append(set_billing_account_action(project_id=project_id, billing_account_id=billing_account_id))
    for api_name in disabled_apis:
        actions.append(disable_api(project_id=project_id, api_name=api_name))
    for api_name in enabled_apis:
        actions.append(enable_api(project_id=project_id, api_name=api_name))
    return {'status': "MISSING", 'actions': actions}


def main():
    stdin: dict = json.loads(sys.stdin.read())
    cfg: dict = stdin['config']

    project_id: str = cfg['project_id']
    organization_id: int = cfg['organization_id'] if 'organization_id' in cfg else None
    billing_account_id: str = cfg['billing_account_id'] if 'billing_account_id' in cfg else None
    enabled_apis: Sequence[str] = cfg['apis']['enabled'] if 'apis' in cfg and 'enabled' in cfg['apis'] else []
    disabled_apis: Sequence[str] = cfg['apis']['disabled'] if 'apis' in cfg and 'disabled' in cfg['apis'] else []

    try:
        print(json.dumps(handle_project_exists(project_id=project_id,
                                               actual_project=find_project(project_id=project_id),
                                               desired_organization_id=organization_id,
                                               desired_billing_account_id=billing_account_id,
                                               desired_enabled_apis=enabled_apis,
                                               desired_disabled_apis=disabled_apis),
                         indent=2))
    except ProjectNotFoundError:
        print(json.dumps(create_missing_project_state(project_id=project_id,
                                                      organization_id=organization_id,
                                                      billing_account_id=billing_account_id,
                                                      enabled_apis=enabled_apis,
                                                      disabled_apis=disabled_apis),
                         indent=2))


if __name__ == "__main__":
    main()
