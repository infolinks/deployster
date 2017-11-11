#!/usr/bin/env python3

import argparse
import json

from deployster.gcp.services import get_container, wait_for_container_projects_zonal_operation


# TODO: review all arguments to all resource actions (nargs, choices, required, etc)

def main():
    argparser = argparse.ArgumentParser(description='Set addon enablement.')
    argparser.add_argument('--project-id', dest='project_id', required=True, metavar='PROJECT-ID',
                           help="the GCP project ID (eg. 'western-evening', or 'backoffice')")
    argparser.add_argument('--zone', required=True, metavar='ZONE', help="the zone of the cluster.")
    argparser.add_argument('--name', required=True, metavar='NAME', help="the name of the target cluster.")
    argparser.add_argument('--addon', required=True, metavar='ADDON',
                           help="the name of the addon to enable or disable.")
    argparser.add_argument('--status', required=True, metavar='ENABLED|DISABLED',
                           help="either 'enabled' or 'disabled'.")
    args = argparser.parse_args()

    op = get_container().projects().zones().addons(projectId=args.project_id,
                                                   zone=args.zone,
                                                   clusterId=args.name,
                                                   body={
                                                       'addonsConfig': {
                                                           args.addon: {
                                                               'disabled': args.status == 'DISABLED'
                                                           }
                                                       }
                                                   })
    result = wait_for_container_projects_zonal_operation(project_id=args.project_id, zone=args.zone, operation=op)
    print(json.dumps({'result': result}))


if __name__ == "__main__":
    main()
