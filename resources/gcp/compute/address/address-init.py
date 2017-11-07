#!/usr/bin/env python3

import json


def main():

    initialization = {
        "requires": {
            "gcloud": "/root/.config/gcloud"
        },
        "state_entrypoint": "/deployster/address-state.py"
    }

    print(json.dumps(initialization))


if __name__ == "__main__":
    main()
