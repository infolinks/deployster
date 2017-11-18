#!/usr/bin/env python3

import argparse

from deployster.gcp.services import get_service_management, wait_for_service_manager_operation


def main():
    argparser: argparse.ArgumentParser = argparse.ArgumentParser(description='Attach GCP project to organization.')
    argparser.add_argument('--project-id', required=True, metavar='ID', help="the alpha-numeric GCP project ID")
    argparser.add_argument('--api', required=True, metavar='NAME', help="the API name (eg. 'cloudbuild.googleapis.com)")
    args = argparser.parse_args()

    op = get_service_management().services().disable(serviceName=args.api,
                                                     body={'consumerId': f"project:{args.project_id}"}).execute()
    wait_for_service_manager_operation(op)


if __name__ == "__main__":
    main()
