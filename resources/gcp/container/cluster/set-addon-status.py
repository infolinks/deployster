#!/usr/bin/env python3

import argparse

from deployster.gcp.services import get_container, wait_for_container_projects_zonal_operation


def main():
    argparser = argparse.ArgumentParser(description='Set addon enablement.')
    argparser.add_argument('--project-id', required=True, metavar='ID', help="the alpha-numeric GCP project ID")
    argparser.add_argument('--zone', required=True, metavar='ZONE', help="the primary zone of the cluster")
    argparser.add_argument('--name', required=True, metavar='NAME', help="the name of the cluster")
    argparser.add_argument('--addon', required=True, metavar='ADDON', help="the addon to enable or disable")
    argparser.add_argument('--status', required=True, metavar='ENABLED|DISABLED', help="new status of the addon")
    args = argparser.parse_args()

    op = get_container().projects().zones().clusters().addons(projectId=args.project_id,
                                                              zone=args.zone,
                                                              clusterId=args.name,
                                                              body={
                                                                  'addonsConfig': {
                                                                      args.addon: {
                                                                          'disabled': args.status == 'DISABLED'
                                                                      }
                                                                  }
                                                              })
    wait_for_container_projects_zonal_operation(project_id=args.project_id, zone=args.zone, operation=op)


if __name__ == "__main__":
    main()
