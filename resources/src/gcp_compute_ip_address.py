#!/usr/bin/env python3.6

import json
import sys
from typing import Sequence

from dresources import DAction, action
from external_services import ExternalServices
from gcp import GcpResource


class GcpIpAddress(GcpResource):

    def __init__(self, data: dict, svc: ExternalServices = ExternalServices()) -> None:
        super().__init__(data=data, svc=svc)
        self.config_schema.update({
            "required": ["project_id", "name"],
            "additionalProperties": False,
            "properties": {
                "project_id": {"type": "string"},
                "region": {"type": "string"},
                "name": {"type": "string"}
            }
        })

    def discover_state(self):
        if 'region' in self.info.config:
            return self.svc.get_gcp_compute_regional_ip_address(project_id=self.info.config['project_id'],
                                                                region=self.info.config['region'],
                                                                name=self.info.config['name'])
        else:
            return self.svc.get_gcp_compute_global_ip_address(project_id=self.info.config['project_id'],
                                                              name=self.info.config['name'])

    def get_actions_for_missing_state(self) -> Sequence[DAction]:
        type = "global" if 'region' not in self.info.config else "regional"
        return [DAction(name=f"create", description=f"Create {type} IP address '{self.info.config['name']}'")]

    def get_actions_for_discovered_state(self, state: dict) -> Sequence[DAction]:
        # addresses either exist or do not exist - there are no properties to update in a GCP regional address
        # therefor if we got to this point (address exists) just return an empty list of actions (nothing to do)
        return []

    @action
    def create(self, args):
        if args: pass
        if 'region' not in self.info.config:
            self.svc.create_gcp_compute_global_ip_address(project_id=self.info.config['project_id'],
                                                          name=self.info.config['name'])
        else:
            self.svc.create_gcp_compute_regional_ip_address(project_id=self.info.config['project_id'],
                                                            region=self.info.config['region'],
                                                            name=self.info.config['name'])


def main():
    GcpIpAddress(json.loads(sys.stdin.read())).execute()  # pragma: no cover


if __name__ == "__main__":
    main()
