#!/usr/bin/env python3

import json
import sys
from typing import Sequence

from googleapiclient.errors import HttpError

from dresources import DAction, action
from gcp import GcpResource
from gcp_services import get_compute, wait_for_compute_region_operation, wait_for_compute_global_operation


class GcpIpAddress(GcpResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
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
        try:
            if 'region' in self.info.config:
                return get_compute().addresses().get(project=self.info.config['project_id'],
                                                     region=self.info.config['region'],
                                                     address=self.info.config['name']).execute()
            else:
                return get_compute().globalAddresses().get(project=self.info.config['project_id'],
                                                           address=self.info.config['name']).execute()
        except HttpError as e:
            if e.resp.status == 404:
                return None
            else:
                raise

    def get_actions_for_missing_state(self) -> Sequence[DAction]:
        type = "global" if 'region' not in self.info.config else "regional"
        return [DAction(name=f"create", description=f"Create {type} IP address '{self.info.config['name']}'")]

    def get_actions_for_discovered_state(self, state: dict) -> Sequence[DAction]:
        # addresses either exist or do not exist - there are no properties to update in a GCP regional address
        # therefor if we got to this point (address exists) just return an empty list of actions (nothing to do)
        # we do validate, however, that the found address is regional if resource is given a region, or alternatively,
        # that the found address is global, if this resource IS NOT given a region
        if 'region' in state and 'region' not in self.info.config:
            raise Exception(f"illegal config: cannot convert a regional IP address to a global IP address")
        elif 'region' not in state and 'region' in self.info.config:
            raise Exception(f"illegal config: cannot convert a global IP address to a regional IP address")
        else:
            return []

    @action
    def create(self, args):
        if args: pass
        if 'region' not in self.info.config:
            addresses_service = get_compute().globalAddresses()
            result = addresses_service.insert(project=self.info.config['project_id'],
                                              body={'name': self.info.config['name']}).execute()
            wait_for_compute_global_operation(project_id=self.info.config['project_id'], operation=result)
        else:
            addresses_service = get_compute().addresses()
            result = addresses_service.insert(project=self.info.config['project_id'],
                                              region=self.info.config['region'],
                                              body={'name': self.info.config['name']}).execute()
            wait_for_compute_region_operation(project_id=self.info.config['project_id'],
                                              region=self.info.config['region'],
                                              operation=result)


def main():
    GcpIpAddress(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
