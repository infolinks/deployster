#!/usr/bin/env python3

import json


def main():
    print(json.dumps({
        "label": "Kubernetes Service Account",
        "required_plugs": {
            "gcloud": "/root/.config/gcloud"
        },
        "required_resources": {
            "namespace": "infolinks/deployster-k8s-namespace"
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
            "entrypoint": "/deployster/service-account-state.py"
        }
    }))


if __name__ == "__main__":
    main()
