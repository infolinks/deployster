#!/usr/bin/env python3

import json


def main():
    print(json.dumps({
        "label": "Kubernetes Cluster",
        "required_plugs": {
            "gcloud": "/root/.config/gcloud"
        },
        "required_resources": {
            "project": "infolinks/deployster/gcp/project"
        },
        "config_schema": {
            "type": "object",
            "required": ["zone", "name"],
            "additionalProperties": False,
            "properties": {
                "zone": {
                    "type": "string"
                },
                "name": {
                    "type": "string"
                },
                "description": {
                    "type": "string"
                },
                "version": {
                    "type": "string"
                },
                "node_pools": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {
                                "type": "string"
                            },
                            "min_size": {
                                "type": "integer"
                            },
                            "max_size": {
                                "type": "integer"
                            },
                            "service_account": {
                                "type": "string"
                            },
                            "oauth_scopes": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "uniqueItems": True
                                }
                            },
                            "preemptible": {
                                "type": "boolean"
                            },
                            "machine_type": {
                                "type": "string"
                            },
                            "disk_size_gb": {
                                "type": "integer"
                            },
                            "tags": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "uniqueItems": True
                                }
                            },
                            "metadata": {
                                "type": "object"
                            },
                            "labels": {
                                "type": "object"
                            }
                        }
                    }
                }
            }
        },
        "state_action": {
            "entrypoint": "/deployster/cluster-state.py"
        }
    }))


if __name__ == "__main__":
    main()
