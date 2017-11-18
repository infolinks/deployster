#!/usr/bin/env python3

import argparse

from deployster.gcp.services import get_container, wait_for_container_projects_zonal_operation


def main():
    argparser = argparse.ArgumentParser(description='Create node pool.')
    argparser.add_argument('--project-id', required=True, metavar='ID', help="the alpha-numeric GCP project ID")
    argparser.add_argument('--zone', required=True, metavar='ZONE', help="the primary zone of the cluster")
    argparser.add_argument('--name', required=True, metavar='NAME', help="the name of the cluster")
    argparser.add_argument('--pool', required=True, metavar='NAME', help="the name of the node pool")
    args = argparser.parse_args()

    operation = get_container().projects().zones().clusters().nodePools().setManagement(
        projectId=args.project_id, zone=args.zone, clusterId=args.name, nodePoolId=args.pool,
        body={
            "management": {
                "autoUpgrade": False
            }
        }).execute()
    wait_for_container_projects_zonal_operation(project_id=args.project_id,
                                                zone=args.zone,
                                                operation=operation,
                                                timeout=900)


if __name__ == "__main__":
    main()
