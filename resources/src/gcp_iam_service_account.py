#!/usr/bin/env python3.6

import argparse
import json
import sys
from typing import Sequence, MutableSequence

from dresources import DAction, action
from external_services import ExternalServices
from gcp import GcpResource


class GcpIamServiceAccount(GcpResource):

    def __init__(self, data: dict, svc: ExternalServices = ExternalServices()) -> None:
        super().__init__(data=data, svc=svc)
        self.config_schema.update({
            "type": "object",
            "required": ["project_id", "name"],
            "additionalProperties": False,
            "properties": {
                "project_id": {"type": "string", "pattern": "^[a-z]([-a-z0-9]*[a-z0-9])$"},
                "name": {"type": "string", "pattern": "^[a-z]([-a-z0-9]*[a-z0-9])$"},
                "display_name": {"type": "string", "minLength": 1}
            }
        })

    def discover_state(self):
        project_id = self.info.config['project_id']
        service_account_name = self.info.config['name']
        return self.svc.find_service_account(project_id, service_account_name)

    def get_actions_for_missing_state(self) -> Sequence[DAction]:
        project_id = self.info.config['project_id']
        service_account_name = self.info.config['name']
        resource_name = f"projects/{project_id}/serviceAccounts/{service_account_name}"
        return [
            DAction(name=f"create-service-account", description=f"Create service account '{resource_name}'")
        ]

    def get_actions_for_discovered_state(self, state: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = []
        project_id = self.info.config['project_id']
        service_account_name = self.info.config['name']
        resource_name = f"projects/{project_id}/serviceAccounts/{service_account_name}"

        display_name = self.info.config['display_name']
        if display_name != state['displayName']:
            actions.append(DAction(name=f"update-display-name",
                                   description=f"Update display name of service account '{resource_name}'",
                                   args=["update_display_name", state['etag']]))

        return actions

    def configure_action_argument_parser(self, action: str, argparser: argparse.ArgumentParser):
        super().configure_action_argument_parser(action, argparser)
        if action == 'update_display_name':
            argparser.add_argument('etag',
                                   type=str,
                                   metavar='ETAG',
                                   help="current ETag of the resource, for safe updates")

    @action
    def create_service_account(self, args):
        if args: pass
        project_id: str = self.info.config['project_id']
        name: str = self.info.config['name']
        display_name: str = self.info.config['display_name'] if 'display_name' in self.info.config else name
        self.svc.create_service_account(project_id=project_id, name=name, display_name=display_name)

    @action
    def update_display_name(self, args):
        project_id: str = self.info.config['project_id']
        name: str = self.info.config['name']
        display_name: str = self.info.config['display_name'] if 'display_name' in self.info.config else name
        self.svc.update_service_account_display_name(project_id=project_id,
                                                     name=name,
                                                     display_name=display_name,
                                                     etag=args.etag)


def main():
    GcpIamServiceAccount(json.loads(sys.stdin.read())).execute()  # pragma: no cover


if __name__ == "__main__":
    main()
