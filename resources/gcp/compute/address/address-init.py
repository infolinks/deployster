#!/usr/bin/env python3

import json


def main():
    print(json.dumps({
        "label": "Reserved IP address",
        "required_plugs": {
            "gcloud": "/root/.config/gcloud"
        },
        "required_resources": {
            "project": "infolinks/deployster-gcp-project"
        },
        "config_schema": {
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
        },
        "state_action": {
            "entrypoint": "/deployster/address-state.py"
        }
    }))


if __name__ == "__main__":
    main()
