#!/usr/bin/env python3

import json


def main():
    print(json.dumps({
        "label": "Kubernetes Namespace",
        "required_plugs": {
            "gcloud": "/root/.config/gcloud"
        },
        "required_resources": {
            "cluster": "infolinks/deployster/gcp/container/cluster"
        },
        "config_schema": {
            "type": "object",
            "required": ["name"],
            "additionalProperties": False,
            "properties": {
                "name": {
                    "type": "string"
                }
            }
        },
        "state_action": {
            "entrypoint": "/deployster/namespace-state.py"
        }
    }))


if __name__ == "__main__":
    main()
