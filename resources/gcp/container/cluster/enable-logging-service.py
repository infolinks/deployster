#!/usr/bin/env python3

import argparse
import json

from deployster.gcp.services import get_container, wait_for_container_projects_zonal_operation


def main():
    argparser = argparse.ArgumentParser(description='Enable logging service.')
    argparser.add_argument('--project-id', dest='project_id', required=True, metavar='PROJECT-ID',
                           help="the GCP project ID (eg. 'western-evening', or 'backoffice')")
    argparser.add_argument('--zone', dest='zone', required=True, metavar='ZONE', help="the zone of the cluster.")
    argparser.add_argument('--name', dest='name', required=True, metavar='NAME', help="the name of the target cluster.")
    args = argparser.parse_args()

    op = get_container().projects().zones().logging(projectId=args.project_id,
                                                    zone=args.zone,
                                                    clusterId=args.name,
                                                    body={
                                                        'loggingService': "logging.googleapis.com"
                                                    })
    result = wait_for_container_projects_zonal_operation(project_id=args.project_id, zone=args.zone, operation=op)
    print(json.dumps({'result': result}))


if __name__ == "__main__":
    main()
