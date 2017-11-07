#!/usr/bin/env python3

import json


def main():
    print(json.dumps({
        "requires": {
            "gcloud": "/root/.config/gcloud"
        },
        "state_entrypoint": "/deployster/project-state.py"
    }))


if __name__ == "__main__":
    main()
