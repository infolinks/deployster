#!/usr/bin/env python3

import argparse
import json
import sys
from typing import Sequence, MutableSequence

from googleapiclient.discovery import build

from dresources import DAction, action
from gcp import GcpResource
from gcp_services import get_resource_manager, get_billing, wait_for_resource_manager_operation, \
    get_service_management, wait_for_service_manager_operation, get_project_enabled_apis


class GcpProject(GcpResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.config_schema.update({
            "type": "object",
            "required": ["project_id"],
            "additionalProperties": False,
            "properties": {
                "project_id": {"type": "string", "pattern": "^[a-zA-Z][a-zA-Z0-9_\\-]*$"},
                "organization_id": {"type": "integer"},
                "billing_account_id": {"type": "string"},
                "apis": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "enabled": {
                            "type": "array",
                            "items": {"type": "string", "uniqueItems": True}
                        },
                        "disabled": {
                            "type": "array",
                            "items": {"type": "string", "uniqueItems": True}
                        }
                    }
                }
            }
        })

    @property
    def project_id(self) -> str:
        return self.resource_config['project_id']

    @property
    def organization_id(self) -> int:
        return self.resource_config['organization_id'] if 'organization_id' in self.resource_config else None

    @property
    def billing_account_id(self) -> str:
        return self.resource_config['billing_account_id'] if 'billing_account_id' in self.resource_config else None

    @property
    def enabled_apis(self) -> Sequence[str]:
        apis: dict = self.resource_config['apis'] if 'apis' in self.resource_config else {}
        return apis['enabled'] if 'enabled' in apis else None

    @property
    def disabled_apis(self) -> Sequence[str]:
        apis: dict = self.resource_config['apis'] if 'apis' in self.resource_config else {}
        return apis['disabled'] if 'disabled' in apis else None

    def discover_actual_properties(self):
        filter: str = f"name:{self.project_id}"
        result: dict = get_resource_manager().projects().list(filter=filter).execute()

        if 'projects' not in result:
            return None

        projects: Sequence[dict] = result['projects']
        if len(projects) == 0:
            return None
        elif len(projects) > 1:
            raise Exception(f"too many GCP projects matched filter '{filter}'")
        else:
            project = projects[0]

            actual_billing: dict = get_billing().projects().getBillingInfo(name=f"projects/{self.project_id}").execute()
            if 'billingAccountName' in actual_billing:
                project['billing_account_id']: str = actual_billing['billingAccountName'][len('billingAccounts/'):]
            else:
                project['billing_account_id']: str = None

            project['apis']: dict = {'enabled': get_project_enabled_apis(project_id=self.project_id)}

            return project

    def get_actions_when_missing(self) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = [
            DAction(name=f"create-project", description=f"Create GCP project '{self.project_id}'"),
            DAction(name='set-billing-account',
                    description=f"Set billing account of '{self.project_id}' to '{self.billing_account_id}'"),
        ]
        if self.enabled_apis:
            for api_name in [api_name for api_name in self.enabled_apis]:
                actions.append(
                    DAction(name=f"enable-api-{api_name}",
                            description=f"Enable API '{api_name}' for '{self.project_id}'",
                            args=['enable_api', api_name]))
        return actions

    def get_actions_when_existing(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = []

        actual_parent: dict = actual_properties['parent'] if 'parent' in actual_properties else {}
        actual_parent_id: int = int(actual_parent['id']) if 'id' in actual_parent else None
        actual_billing: dict = get_billing().projects().getBillingInfo(name=f"projects/{self.project_id}").execute()
        actual_billing_account_id: str = actual_billing['billingAccountName'][len('billingAccounts/'):] \
            if 'billingAccountName' in actual_billing else None

        # update project organization if necessary
        if self.organization_id != actual_parent_id:
            actions.append(DAction(name='set-organization',
                                   description=f"Set organization of '{self.project_id}' to '{self.organization_id}'"))

        # update project billing account if necessary
        if self.billing_account_id != actual_billing_account_id:
            actions.append(
                DAction(name='set-billing-account',
                        description=f"Set billing account of '{self.project_id}' to '{self.billing_account_id}'"))

        # fetch currently enabled project APIs
        actual_enabled_api_names: Sequence[str] = get_project_enabled_apis(project_id=self.project_id)

        # disable APIs that user desires to be disable, if currently enabled
        if self.disabled_apis:
            for api_name in [api_name for api_name in self.disabled_apis if api_name in actual_enabled_api_names]:
                actions.append(
                    DAction(name=f"disable-api-{api_name}",
                            description=f"Disable API '{api_name}' for '{self.project_id}'",
                            args=['disable_api', api_name]))

        # enable APIs that user desires to be enabled, if not already enabled
        if self.enabled_apis:
            for api_name in [api_name for api_name in self.enabled_apis if api_name not in actual_enabled_api_names]:
                actions.append(
                    DAction(name=f"enable-api-{api_name}",
                            description=f"Enable API '{api_name}' for '{self.project_id}'",
                            args=['enable_api', api_name]))

        return actions

    def define_action_args(self, action: str, argparser: argparse.ArgumentParser):
        super().define_action_args(action, argparser)
        if action == 'disable_api':
            argparser.add_argument('api', metavar='API-NAME', help="API to disable (eg. 'cloudbuild.googleapis.com)")
        elif action == 'enable_api':
            argparser.add_argument('api', metavar='API-NAME', help="API to enable (eg. 'cloudbuild.googleapis.com)")

    @action
    def set_organization(self, args):
        if args: pass
        cloud_resource_manager = build(serviceName='cloudresourcemanager', version='v1')
        body = {'parent': {'type': 'organization', 'id': str(self.organization_id)} if self.organization_id else None}
        result = cloud_resource_manager.projects().update(projectId=self.project_id, body={body}).execute()
        wait_for_resource_manager_operation(result)

    @action
    def set_billing_account(self, args):
        if args: pass
        body = {"billingAccountName": f"billingAccounts/{self.billing_account_id}" if self.billing_account_id else ""}
        get_billing().projects().updateBillingInfo(name='projects/' + self.project_id, body=body).execute()

    @action
    def disable_api(self, args):
        body = {'consumerId': f"project:{self.project_id}"}
        op = get_service_management().services().disable(serviceName=args.api, body=body).execute()
        wait_for_service_manager_operation(op)

    @action
    def enable_api(self, args):
        body = {'consumerId': f"project:{self.project_id}"}
        op = get_service_management().services().enable(serviceName=args.api, body=body).execute()
        wait_for_service_manager_operation(op)

    @action
    def create_project(self, args):
        if args: pass
        projects_service = build(serviceName='cloudresourcemanager', version='v1').projects()
        wait_for_resource_manager_operation(projects_service.create(body={
            "projectId": self.project_id,
            "name": self.project_id,
            "parent": {
                'type': 'organization',
                'id': str(self.organization_id)
            } if self.organization_id else None
        }).execute())


def main():
    GcpProject(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
