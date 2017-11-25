#!/usr/bin/env python3

import json
import sys
from typing import Sequence, Mapping

from googleapiclient.errors import HttpError

from dresources import DResource, DAction, action
from gcp_project import GcpProject
from gcp_services import get_compute, wait_for_compute_region_operation, wait_for_compute_global_operation


class GcpIpAddress(DResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self._project: GcpProject = None

    @property
    def project(self) -> GcpProject:
        if self._project is None:
            self._project: GcpProject = GcpProject(self.get_resource_dependency('project'))
        return self._project

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
            raise Exception(f"address not available")

    @property
    def resource_required_plugs(self) -> Mapping[str, str]:
        return {
            "gcloud": "/root/.config/gcloud"
        }

    @property
    def resource_required_resources(self) -> Mapping[str, str]:
        return {
            "project": "infolinks/deployster-gcp-project"
        }

    @property
    def resource_config_schema(self) -> dict:
        return {
            "type": "object",
            "required": ["name"],
            "additionalProperties": False,
            "properties": {
                "region": {
                    "type": "string"
                },
                "name": {
                    "type": "string"
                }
            }
        }

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

    def infer_actions_from_actual_properties(self, actual_properties: dict) -> Sequence[DAction]:
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

    @property
    def actions_for_missing_status(self) -> Sequence[DAction]:
        type = "global" if self.region is None else "regional"
        return [DAction(name=f"create", description=f"Create {type} IP address called '{self.name}'")]

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
