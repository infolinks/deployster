#!/usr/bin/env python3

import json
import subprocess
import sys
from abc import abstractmethod
from typing import Sequence, MutableSequence

from dresources import action, DAction, collect_differences
from k8s_resources import K8sResource


class K8sSpecificationResource(K8sResource):

    @abstractmethod
    def __init__(self, data: dict) -> None:
        super().__init__(data)

    @property
    @abstractmethod
    def spec(self) -> str:
        raise Exception(f"illegal state: 'state' not implemented for '{type(self)}' resource type")

    @property
    def resource_config_schema(self) -> dict:
        schema = super().resource_config_schema
        schema['properties']['spec'] = {"type": "object"}
        return schema

    def infer_actions_from_actual_properties(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = super().infer_actions_from_actual_properties(actual_properties)

        diffs = collect_differences(desired=self.spec, actual=actual_properties["spec"], path=["spec"])
        if diffs:
            actions.append(
                DAction(name='update-specification', description=f"Update {self.k8s_kind.lower()} specification"))

        return actions

    def build_manifest(self) -> dict:
        manifest = super().build_manifest()
        manifest['spec'] = self.spec
        return manifest

    @action
    def create(self, args) -> None:
        super().create(args)
        if not self.wait_for_resource(self.validate_status):
            namespace_arg = f"--namespace {self.namespace.name}" if self.namespace is not None else ""
            print(f"{self.k8s_kind} '{self.name}' failed to successfully deploy for {self.timeout} seconds.",
                  file=sys.stderr)
            print(f"use this command to find out more:", file=sys.stderr)
            print(f"    kubectl get {self.k8s_kind.lower()} {self.name} {namespace_arg} -o yaml", file=sys.stderr)
            exit(1)

    @action
    def update_spec(self, args) -> None:
        if args: pass

        namespace_arg = f"--namespace {self.namespace.name}" if self.namespace is not None else ""
        command = f"kubectl patch {self.k8s_kind.lower()} {self.name} {namespace_arg}" \
                  f"    --type=merge " \
                  f"    --patch '{json.dumps({'spec':self.spec})}'"
        subprocess.run(command, check=True, timeout=self.timeout, shell=True)

        if not self.wait_for_resource(self.validate_status):
            namespace_arg = f"--namespace {self.namespace.name}" if self.namespace is not None else ""
            print(f"{self.k8s_kind} '{self.name}' failed to successfully deploy for {self.timeout} seconds.",
                  file=sys.stderr)
            print(f"use this command to find out more:", file=sys.stderr)
            print(f"    kubectl get {self.k8s_kind.lower()} {self.name} {namespace_arg} -o yaml", file=sys.stderr)
            exit(1)

    @abstractmethod
    def validate_status(self, result: dict) -> bool:
        raise Exception(f"illegal state: 'validate_status' not implemented for '{type(self)}' resource type")
