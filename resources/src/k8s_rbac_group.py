#!/usr/bin/env python3

import json
import sys
from typing import Sequence

from dresources import DResource, DAction


class K8sRbacGroup(DResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.config_schema.update({
            "required": ["name"],
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string"}
            }
        })

    @property
    def name(self) -> str:
        return self.resource_config['name']

    @property
    def k8s_kind(self) -> str:
        return "Group"

    def discover_actual_properties(self):
        return {}

    def get_actions_when_missing(self) -> Sequence[DAction]:
        return []

    def get_actions_when_existing(self, actual_properties: dict) -> Sequence[DAction]:
        return []


def main():
    K8sRbacGroup(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
