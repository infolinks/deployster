#!/usr/bin/env python3

import argparse

from deployster.gcp.services import get_container, wait_for_container_projects_zonal_operation


def main():
    argparser = argparse.ArgumentParser(description='Update cluster master version.')
    argparser.add_argument('--project-id', required=True, metavar='ID', help="the alpha-numeric GCP project ID")
    argparser.add_argument('--zone', required=True, metavar='ZONE', help="the primary zone of the cluster")
    argparser.add_argument('--name', required=True, metavar='NAME', help="the name of the cluster")
    argparser.add_argument('--version', required=True, metavar='VERSION', help="cluster master version")
    args = argparser.parse_args()

    op = get_container().projects().zones().clusters().master(projectId=args.project_id,
                                                              zone=args.zone,
                                                              clusterId=args.name,
                                                              body={
                                                                  'masterVersion': args.version
                                                              }).execute()
    wait_for_container_projects_zonal_operation(project_id=args.project_id, zone=args.zone, operation=op)


if __name__ == "__main__":
    main()
