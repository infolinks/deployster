#!/usr/bin/env python3

import json


def main():
    print(json.dumps({
        "label": "Project",
        "required_plugs": {
            "gcloud": "/root/.config/gcloud"
        },
        "config_schema": {
            "type": "object",
            "required": ["project_id"],
            "additionalProperties": False,
            "properties": {
                "project_id": {
                    "type": "string",
                    "pattern": "^[a-zA-Z][a-zA-Z0-9_\\-]*$"
                },
                "organization_id": {
                    "type": "integer"
                },
                "billing_account_id": {
                    "type": "string"
                },
                "apis": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "enabled": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "uniqueItems": True
                            }
                        },
                        "disabled": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "uniqueItems": True
                            }
                        }
                    }
                }
            }
        },
        "state_action": {
            "entrypoint": "/deployster/project-state.py"
        }
    }))


if __name__ == "__main__":
    main()
