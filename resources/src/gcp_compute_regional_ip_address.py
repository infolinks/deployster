#!/usr/bin/env python3

import json
import sys
from typing import Sequence, Mapping

from googleapiclient.errors import HttpError

from dresources import DResource, DAction, action
from gcp_project import GcpProject
from gcp_services import get_compute, wait_for_compute_region_operation


class GcpRegionalAddress(DResource):

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
        return self.resource_config['region']

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
            "required": ["name", "region"],
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
            return get_compute().addresses().get(project=self.project.project_id,
                                                 region=self.region,
                                                 address=self.name).execute()
        except HttpError as e:
            if e.resp.status == 404:
                return None
            else:
                raise

    def infer_actions_from_actual_properties(self, actual_properties: dict) -> Sequence[DAction]:
        # addresses either exist or do not exist - there are no properties to update in a GCP regional address
        # therefor if we got to this point (address exists) just return an empty list of actions (nothing to do)
        return []

    @property
    def actions_for_missing_status(self) -> Sequence[DAction]:
        return [DAction(name=f"create", description=f"Create regional IP address '{self.region}/{self.name}'")]

    @action
    def create(self, args):
        if args: pass
        addresses_service = get_compute().addresses()
        result = addresses_service.insert(project=self.project.project_id,
                                          region=self.region,
                                          body={'name': self.name}).execute()
        wait_for_compute_region_operation(project_id=self.project.project_id, region=self.region, operation=result)


def main():
    GcpRegionalAddress(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
