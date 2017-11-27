#!/usr/bin/env python3

import json
import sys
from typing import Sequence

from googleapiclient.errors import HttpError

from dresources import DAction, action
from gcp import GcpResource
from gcp_project import GcpProject
from gcp_services import get_compute, wait_for_compute_region_operation, wait_for_compute_global_operation


class GcpIpAddress(GcpResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.add_dependency(name='project', type='infolinks/deployster-gcp-project', optional=False, factory=GcpProject)
        self.config_schema.update({
            "required": ["name"],
            "additionalProperties": False,
            "properties": {
                "region": {"type": "string"},
                "name": {"type": "string"}
            }
        })

    @property
    def project(self) -> GcpProject:
        return self.get_dependency('project')

    @property
    def region(self) -> str:
        return self.resource_config['region'] if 'region' in self.resource_config else None

    @property
    def name(self) -> str:
        return self.resource_config['name']

    @property
    def ip_address(self) -> str:
        if self.resource_properties is not None and 'address' in self.resource_properties:
            return self.resource_properties['address']
        else:
            raise Exception(f"actual IP address not available")

    def discover_actual_properties(self):
        try:
            if self.region is not None:
                return get_compute().addresses().get(project=self.project.project_id,
                                                     region=self.region,
                                                     address=self.name).execute()
            else:
                return get_compute().globalAddresses().get(project=self.project.project_id, address=self.name).execute()
        except HttpError as e:
            if e.resp.status == 404:
                return None
            else:
                raise

    def get_actions_when_missing(self) -> Sequence[DAction]:
        type = "global" if self.region is None else "regional"
        return [DAction(name=f"create", description=f"Create {type} IP address called '{self.name}'")]

    def get_actions_when_existing(self, actual_properties: dict) -> Sequence[DAction]:
        # addresses either exist or do not exist - there are no properties to update in a GCP regional address
        # therefor if we got to this point (address exists) just return an empty list of actions (nothing to do)
        # we do validate, however, that the found address is regional if resource is given a region, or alternatively,
        # that the found address is global, if this resource IS NOT given a region
        if 'region' in actual_properties and self.region is None:
            raise Exception(f"illegal state: expecting global IP address, but found a regional IP address instead")
        elif 'region' not in actual_properties and self.region is not None:
            raise Exception(f"illegal state: expecting regional IP address, but found a global IP address instead")
        else:
            return []

    @action
    def create(self, args):
        if args: pass
        if self.region is None:
            addresses_service = get_compute().globalAddresses()
            result = addresses_service.insert(project=self.project.project_id,
                                              body={'name': self.name}).execute()
            wait_for_compute_global_operation(project_id=self.project.project_id, operation=result)
        else:
            addresses_service = get_compute().addresses()
            result = addresses_service.insert(project=self.project.project_id,
                                              region=self.region,
                                              body={'name': self.name}).execute()
            wait_for_compute_region_operation(project_id=self.project.project_id, region=self.region, operation=result)


def main():
    GcpIpAddress(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
