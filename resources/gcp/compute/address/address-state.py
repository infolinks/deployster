#!/usr/bin/env python3

import json
import sys

from googleapiclient.errors import HttpError

from deployster.gcp.services import get_compute


def main():
    params = json.loads(sys.stdin.read())
    try:
        address = get_compute().addresses().get(project=params['properties']['project']['project_id'],
                                                region=params['properties']['region'],
                                                address=params['name']).execute()
        print(json.dumps(address, indent=2), file=sys.stderr)
        state = {
            'status': 'VALID',
            'actions': [],
            'properties': {
            }
        }
    except HttpError as e:
        if e.resp.status == 404:
            state = {
                'status': 'MISSING',
                'actions': [
                    {
                        'name': 'create-address',
                        'description': f"Create GCP address",
                        'entrypoint': '/deployster/create-address.py'
                    }
                ],
                'properties': {}
            }
        else:
            state = {
                'status': 'INVALID',
                'reason': str(e)
            }

    # except TooManyProjectsMatchError:
    #     state = {
    #         'status': "INVALID",
    #         'reason': "more than one project is named '%s'" % params['name']
    #     }

    # except ProjectNotFoundError:
    #     actions = [create_project_action(params)]
    #     if 'billing_account_id' in params:
    #         actions.append(set_billing_account_action(params['name'], params['billing_account_id']))
    #     for api_name in params['properties']['apis']['disabled']:
    #         actions.append(disable_api(params['name'], api_name))
    #     for api_name in params['properties']['apis']['enabled']:
    #         actions.append(enable_api(params['name'], api_name))
    #     state = {
    #         'status': "MISSING",
    #         'actions': actions
    #     }

    print(json.dumps(state))


if __name__ == "__main__":
    main()
