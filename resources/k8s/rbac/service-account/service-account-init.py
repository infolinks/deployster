#!/usr/bin/env python3

import json


def main():
    print(json.dumps({
        "requires": {
            "gcloud": "/root/.config/gcloud",
            "kube": "/root/.kube"
        },
        "state_entrypoint": "/deployster/service-account-state.py"
    }))


if __name__ == "__main__":
    main()
