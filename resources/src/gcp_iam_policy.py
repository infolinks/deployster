#!/usr/bin/env python3.6
import argparse
import json
import sys
from copy import deepcopy
from typing import Sequence, MutableSequence, List

from dresources import DAction, action
from external_services import ExternalServices
from gcp import GcpResource


class GcpIamPolicy(GcpResource):

    def __init__(self, data: dict, svc: ExternalServices = ExternalServices()) -> None:
        super().__init__(data=data, svc=svc)
        self.config_schema.update({
            "type": "object",
            "required": ["project_id", "bindings"],
            "additionalProperties": False,
            "properties": {
                "project_id": {"type": "string", "pattern": "^[a-z]([-a-z0-9]*[a-z0-9])$"},
                "bindings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "role": {"type": "string"},
                            "members": {
                                "type": "array",
                                "minLength": 1,
                                "items": {"type": "string"}
                            }
                        }
                    }
                }
            }
        })

    def discover_state(self):
        return self.svc.get_project_iam_policy(project_id=self.info.config['project_id'])

    def get_actions_for_missing_state(self) -> Sequence[DAction]:
        raise Exception(f"illegal state: IAM policy could not be fetched! (permissions problem, or missing project?)")

    def get_actions_for_discovered_state(self, state: dict) -> Sequence[DAction]:
        if 'bindings' not in state:
            raise Exception(
                f"illegal state: IAM policy could not be fetched! (permissions problem, or missing project?)")

        update_needed: bool = False
        final_bindings: List[dict] = deepcopy(state['bindings'])
        for desired_binding in self.info.config['bindings']:
            desired_role: str = desired_binding['role']
            desired_members: Sequence[str] = desired_binding['members']
            role_found: bool = False
            for actual_binding in final_bindings:
                if desired_role == actual_binding['role']:
                    role_found = True
                    actual_members: List[str] = actual_binding['members']
                    missing_members = [member for member in desired_members if member not in actual_members]
                    if len(missing_members) > 0:
                        print(f"Subjects {missing_members} missing from role '{desired_role}'", file=sys.stderr)
                        update_needed = True

            if not role_found:
                print(f"No policy for role '{desired_role}' was found", file=sys.stderr)
                update_needed = True

        if update_needed:
            return [DAction(name=f"update-policy",
                            description=f"Update IAM policy",
                            args=["update_policy", state['etag']])]
        else:
            return []

    def configure_action_argument_parser(self, action: str, argparser: argparse.ArgumentParser):
        super().configure_action_argument_parser(action, argparser)
        if action == 'update_policy':
            argparser.add_argument('etag',
                                   type=str,
                                   metavar='ETAG',
                                   help="current ETag of the policy, for safe updates")

    @action
    def update_policy(self, args):
        state: dict = self.info.stale_state

        final_bindings: List[dict] = deepcopy(state['bindings'])
        for desired_binding in self.info.config['bindings']:
            desired_role: str = desired_binding['role']
            desired_members: Sequence[str] = desired_binding['members']
            role_found: bool = False
            for actual_binding in final_bindings:
                if desired_role == actual_binding['role']:
                    actual_members: List[str] = actual_binding['members']
                    actual_members.extend([member for member in desired_members if member not in actual_members])
                    role_found: bool = True
                    break

            if not role_found:
                final_bindings.append({
                    'role': desired_role,
                    'members': desired_members
                })

        self.svc.update_project_iam_policy(project_id=self.info.config['project_id'],
                                           etag=args.etag,
                                           bindings=final_bindings,
                                           verbose=self.info.verbose)


def main():
    GcpIamPolicy(json.loads(sys.stdin.read())).execute()  # pragma: no cover


if __name__ == "__main__":
    main()
