#!/usr/bin/env python3

import argparse
import json

from deployster.gcp.services import get_service_management, wait_for_service_manager_operation


def main():
    argparser = argparse.ArgumentParser(description='Attach GCP project to organization.')
    argparser.add_argument('--project-id', dest='project_id', required=True, metavar='PROJECT-ID',
                           help="the GCP project ID (eg. 'western-evening', or 'backoffice')")
    argparser.add_argument('--api', dest='api', required=True,
                           metavar='API-NAME',
                           help="the API name (eg. 'cloudbuild.googleapis.com)")
    args = argparser.parse_args()

    service_management_service = get_service_management().services()

    op = service_management_service.disable(serviceName=args.api,
                                            body={'consumerId': f"project:{args.project_id}"}).execute()
    result = wait_for_service_manager_operation(op)
    print(json.dumps({'result': result}))


if __name__ == "__main__":
    main()
