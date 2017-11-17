#!/usr/bin/env python3

import argparse

from deployster.gcp.services import get_compute, wait_for_compute_region_operation


def main():
    argparser: argparse.ArgumentParser = argparse.ArgumentParser(description='Create GCP Compute address.')
    argparser.add_argument('--project-id', required=True, metavar='ID', help="the alpha-numeric GCP project ID")
    argparser.add_argument('--region', required=True, metavar='REGION', help="region to create the address in")
    argparser.add_argument('--name', required=True, metavar='NAME', help="the name of the IP address")
    args = argparser.parse_args()

    addresses_service = get_compute().addresses()
    result = addresses_service.insert(project=args.project_id, region=args.region, body={'name': args.name}).execute()
    wait_for_compute_region_operation(project_id=args.project_id, region=args.region, operation=result)


if __name__ == "__main__":
    main()
