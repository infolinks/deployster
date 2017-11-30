#!/usr/bin/env python3

import json
import sys
import time
from copy import deepcopy
from typing import Mapping, Sequence, MutableSequence

from dresources import DAction, action
from gcp import GcpResource
from gcp_project import GcpProject
from gcp_services import get_sql, region_from_zone, wait_for_sql_operation, get_project_enabled_apis, \
    get_service_management, wait_for_service_manager_operation


class GcpCloudSql(GcpResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.add_dependency(name='project', type='infolinks/deployster-gcp-project', optional=False, factory=GcpProject)
        self.config_schema.update({
            "type": "object",
            "required": ["zone", "name", "machine-type"],
            "additionalProperties": False,
            "properties": {
                "zone": {"type": "string"},
                "name": {"type": "string"},
                "machine-type": {
                    "type": "string",
                    "enum": [
                        "db-f1-micro",
                        "db-g1-small",
                        "db-n1-standard-1",
                        "db-n1-standard-2",
                        "db-n1-standard-4",
                        "db-n1-standard-8",
                        "db-n1-standard-16",
                        "db-n1-standard-32",
                        "db-n1-standard-64",
                        "db-n1-highmem-2",
                        "db-n1-highmem-4",
                        "db-n1-highmem-8",
                        "db-n1-highmem-16",
                        "db-n1-highmem-32",
                        "db-n1-highmem-64",
                    ]
                },
                "backup": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["enabled"],
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "time": {
                            "type": "string",
                            "pattern": "^[0-9]{2}:[0-9]{2}$"
                        }
                    }
                },
                "data-disk-size-gb": {
                    "type": "integer",
                    "minimum": 10
                },
                "data-disk-type": {
                    "type": "string",
                    "enum": ["PD_SSD", "PD_HDD"]
                },
                "flags": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string"},
                            "value": {"type": "string"}
                        }
                    }
                },
                "require-ssl": {"type": "boolean"},
                "authorized-networks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["name", "value"],
                        "properties": {
                            "expirationTime": {"type": "string"},  # RFC 3339 format (eg.for 2012-11-15T16:19:00.094Z)
                            "name": {"type": "string"},
                            "value": {"type": "string"}
                        }
                    }
                },
                "maintenance": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["day", "hour"],
                    "properties": {
                        "day": {
                            "oneOf": [
                                {
                                    "type": "string",
                                    "enum": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                                             "Saturday"]
                                },
                                {
                                    "type": "integer",
                                    "minimum": 1,
                                    "maximum": 7,
                                    "exclusiveMaximum": False
                                }
                            ]
                        },
                        "hour": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 23,
                            "exclusiveMaximum": False
                        }
                    }
                },
                "storage-auto-resize": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["enabled"],
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "limit": {
                            "type": "integer",
                            "minimum": 0
                        }
                    }
                },
                "labels": {
                    "type": "object",
                    "additionalProperties": False,
                    "patternProperties": {
                        ".+": {"type": "string"}
                    }
                }
            }
        })

    @property
    def project(self) -> GcpProject:
        return self.get_dependency('project')

    @property
    def zone(self) -> str:
        return self.resource_config['zone']

    @property
    def name(self) -> str:
        return self.resource_config['name']

    @property
    def machine_type(self) -> str:
        return self.resource_config['machine-type']

    @property
    def backup(self) -> dict:
        return self.resource_config['backup'] if 'backup' in self.resource_config else None

    @property
    def data_disk_size_gb(self) -> int:
        return self.resource_config["data-disk-size-gb"] if "data-disk-size-gb" in self.resource_config else None

    @property
    def data_disk_type(self) -> str:
        return self.resource_config["data-disk-type"] if "data-disk-type" in self.resource_config else None

    @property
    def flags(self) -> Sequence[Mapping[str, str]]:
        return self.resource_config["flags"] if "flags" in self.resource_config else None

    @property
    def require_ssl(self) -> bool:
        return self.resource_config["require-ssl"] if "require-ssl" in self.resource_config else None

    @property
    def authorized_networks(self) -> Sequence[Mapping[str, str]]:
        return self.resource_config["authorized-networks"] if "authorized-networks" in self.resource_config else None

    @property
    def maintenance_window(self) -> Mapping[str, int]:
        if "maintenance" in self.resource_config:
            maintenance = deepcopy(self.resource_config["maintenance"])
            if type(maintenance['day']) == str:
                if maintenance['day'] == 'Monday':
                    maintenance['day'] = 1
                elif maintenance['day'] == 'Tuesday':
                    maintenance['day'] = 2
                elif maintenance['day'] == 'Wednesday':
                    maintenance['day'] = 3
                elif maintenance['day'] == 'Thursday':
                    maintenance['day'] = 4
                elif maintenance['day'] == 'Friday':
                    maintenance['day'] = 5
                elif maintenance['day'] == 'Saturday':
                    maintenance['day'] = 6
                elif maintenance['day'] == 'Sunday':
                    maintenance['day'] = 7
                else:
                    raise Exception(f"illegal maintenance day encountered: {maintenance['day']}")
            return maintenance
        else:
            # noinspection PyTypeChecker
            return None

    @property
    def storage_auto_resize(self) -> dict:
        return self.resource_config['storage-auto-resize'] if 'storage-auto-resize' in self.resource_config else None

    @property
    def labels(self) -> Mapping[str, str]:
        return self.resource_config["labels"] if "labels" in self.resource_config else None

    def discover_actual_properties(self):
        sql = get_sql()

        allowed_flags = \
            {flag['name']: flag for flag in sql.flags().list(databaseVersion='MYSQL_5_7').execute()['items']}
        for desired_flag in self.flags:
            desired_name = desired_flag['name']
            if desired_name not in allowed_flags:
                raise Exception(f"flag '{desired_name}' is not a supported MySQL 5.7 flag.")

            allowed_flag = allowed_flags[desired_name]
            flag_type = allowed_flag['type']
            if flag_type == 'NONE':
                if 'value' in desired_flag:
                    raise Exception(f"flag '{desired_name}' does not accept values.")

            elif flag_type == 'INTEGER':
                if 'value' not in desired_flag:
                    raise Exception(f"flag '{desired_name}' requires a value.")
                try:
                    int_value = int(desired_flag['value'])
                except ValueError as e:
                    raise Exception(f"flag '{desired_name}' value must be an integer") from e

                if 'minValue' in allowed_flag and int_value < int(allowed_flag['minValue']):
                    raise Exception(f"flag '{desired_name}' value must be greater than {allowed_flag['minValue']}")
                if 'maxValue' in allowed_flag and int_value > int(allowed_flag['maxValue']):
                    raise Exception(f"flag '{desired_name}' value must not be greater than {allowed_flag['maxValue']}")

            elif flag_type == 'STRING':
                if 'value' not in desired_flag:
                    raise Exception(f"flag '{desired_name}' requires a value.")
                elif 'allowedStringValues' in allowed_flag:
                    allowed_values = allowed_flag['allowedStringValues']
                    if desired_flag['value'] not in allowed_values:
                        raise Exception(f"flag '{desired_name}' value must be one of: {allowed_values}")

            elif flag_type == 'BOOLEAN':
                if 'value' not in desired_flag:
                    raise Exception(f"flag '{desired_name}' requires a value.")
                elif desired_flag['value'] not in ['yes', 'no']:
                    raise Exception(f"flag '{desired_name}' value must be 'on' or 'off'.")

        # if the SQL Admin API is not enabled, there can be no SQL instances; we will, however, have to enable
        # that API for the project later on.
        enabled_apis = get_project_enabled_apis(project_id=self.project.project_id)
        if 'sqladmin.googleapis.com' in enabled_apis and 'sql-component.googleapis.com' in enabled_apis:
            # using "instances().list(..)" because "get" throws 403 when instance does not exist
            # also, it seems the "filter" parameter for "list" does not work; so we fetch all instances and filter here
            result = sql.instances().list(project=self.project.project_id).execute()
            if 'items' in result:
                for instance in result['items']:
                    if instance['name'] == self.name:
                        return instance
        return None

    def get_actions_when_missing(self) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = []

        enabled_apis = get_project_enabled_apis(project_id=self.project.project_id)
        if 'sqladmin.googleapis.com' not in enabled_apis or 'sql-component.googleapis.com' not in enabled_apis:
            # if the SQL Admin API is not enabled, there can be no SQL instances; we will, however, have to enable
            # that API for the project later on.
            actions.append(DAction(name='enable-sqladmin-apis',
                                   description=f"Enable SQL APIs for project '{self.project.project_id}'"))

        actions.append(DAction(name=f"create-sql-instance", description=f"Create SQL instance '{self.name}'"))

        # TODO: support data initializer scripts (ignore script "conditions" here, since database will be fresh)

        return actions

    def get_actions_when_existing(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = []
        actual = actual_properties
        actual_settings = actual['settings']

        # validate instance is RUNNING
        if actual['state'] != "RUNNABLE":
            raise Exception(f"Instance exists, but not running ('{actual['state']}')")

        # validate instance region
        desired_region = region_from_zone(self.zone)
        if actual['region'] != desired_region:
            raise Exception(f"SQL instance is in region '{actual['region']}' instead of '{desired_region}'. "
                            f"Unfortunately, changing SQL instances regions is not allowed in Google Cloud SQL.")

        # validate instance preferred zone
        if actual_settings['locationPreference']['zone'] != self.zone:
            actions.append(DAction(name='update-zone',
                                   description=f"Update SQL instance preferred zone to '{self.zone}'"))

        # validate instance machine type
        if actual_settings['tier'] != self.machine_type:
            actions.append(DAction(name='update-machine-type',
                                   description=f"Update SQL instance machine type zone to '{self.machine_type}'"))

        # validate backup configuration
        desired_backup: dict = self.backup
        if desired_backup is not None:
            if desired_backup['enabled']:
                # Verify that actual backup configuration IS enabled:

                if 'backupConfiguration' not in actual_settings:
                    actions.append(DAction(name='update-backup', description=f"Enable SQL instance backups"))
                else:
                    actual_backup = actual_settings['backupConfiguration']
                    if not actual_backup['enabled'] or not actual_backup['binaryLogEnabled']:
                        actions.append(DAction(name='update-backup',
                                               description=f"Enable SQL instance backup/binary-logging"))
                    elif 'time' in desired_backup:
                        desired_time = desired_backup['time']
                        if desired_time != actual_backup['startTime']:
                            actions.append(
                                DAction(name='update-backup',
                                        description=f"Update SQL instance backup schedule to '{desired_time}'"))
            elif 'time' in desired_backup:
                raise Exception(f"illegal config: cannot specify backup time when backup is disabled")
            elif 'backupConfiguration' in actual_settings:
                # Verify that actual backup configuration IS NOT enabled:
                actual_backup = actual_settings['backupConfiguration']
                if actual_backup['enabled'] or actual_backup['binaryLogEnabled']:
                    actions.append(DAction(name='update-backup',
                                           description=f"Disable SQL instance backups/binary-logging"))
                elif 'time' in desired_backup:
                    raise Exception(f"illegal config: cannot specify backup time when backup is disabled")

        # validate data-disk size
        if self.data_disk_size_gb is not None:
            actual_disk_size: int = int(actual_settings['dataDiskSizeGb'])
            if actual_disk_size != self.data_disk_size_gb:
                if self.data_disk_size_gb < actual_disk_size:
                    raise Exception(
                        f"illegal config: cannot reduce disk size from {actual_disk_size}gb to "
                        f"{self.data_disk_size_gb}gb (not allowed by Cloud SQL APIs).")
                else:
                    actions.append(
                        DAction(name='update-data-disk-size',
                                description=f"Update SQL instance data disk size from {actual_disk_size}gb to "
                                            f"{self.data_disk_size_gb}gb"))

        # validate data-disk type
        if self.data_disk_type is not None:
            if actual_settings['dataDiskType'] != self.data_disk_type:
                actions.append(DAction(name='update-data-disk-type',
                                       description=f"Update SQL instance data disk type to '{self.data_disk_type}'"))

        # validate MySQL flags
        if self.flags is not None:
            actual_flags = actual_settings['databaseFlags'] if 'databaseFlags' in actual_settings else []
            if actual_flags != self.flags:
                actions.append(DAction(name='update-flags', description=f"Update SQL instance flags"))

        # validate SSL connections requirement
        if self.require_ssl is not None:
            if actual_settings['ipConfiguration']['requireSsl'] != self.require_ssl:
                actions.append(
                    DAction(name='update-require-ssl',
                            description=f"Update SQL instance to require SSL connections"))

        # validate authorized networks
        if self.authorized_networks is not None:
            actual_auth_networks = actual_settings['ipConfiguration']['authorizedNetworks']
            if len(actual_auth_networks) != len(self.authorized_networks):
                actions.append(DAction(name='update-authorized-networks',
                                       description=f"Update SQL instance authorized networks"))
            else:
                # validate network names are unique
                names = set()
                for desired_network in self.authorized_networks:
                    if desired_network['name'] in names:
                        raise Exception(f"illegal config: network '{desired_network['name']}' defined more than once")
                    else:
                        names.add(desired_network['name'])

                # validate each network
                for desired_network in self.authorized_networks:
                    try:
                        actual_network = next(n for n in actual_auth_networks if n['name'] == desired_network['name'])
                        desired_expiry = desired_network['expirationTime'] \
                            if 'expirationTime' in desired_network else None
                        actual_expiry = actual_network['expirationTime'] if 'expirationTime' in actual_network else None
                        if desired_network['name'] != actual_network['name'] \
                                or desired_network['value'] != actual_network['value'] \
                                or desired_expiry != actual_expiry:
                            actions.append(DAction(name='update-authorized-networks',
                                                   description=f"Update SQL instance authorized networks "
                                                               f"(found stale network: {desired_network['name']})"))
                            break
                    except StopIteration:
                        actions.append(DAction(name='update-authorized-networks',
                                               description=f"Update SQL instance authorized networks"))
                        break

        # validate maintenance window
        if self.maintenance_window is not None:
            actual_maintenance_window = actual_settings['maintenanceWindow']
            if self.maintenance_window['day'] != actual_maintenance_window['day'] \
                    or self.maintenance_window['hour'] != actual_maintenance_window['hour']:
                actions.append(DAction(name='update-maintenance-window',
                                       description=f"Update SQL instance maintenance window"))

        # validate storage auto-resize
        if self.storage_auto_resize is not None:
            if not self.storage_auto_resize['enabled'] and 'limit' in self.storage_auto_resize:
                raise Exception(f"illegal config: cannot specify storage auto-resize limit when it's disabled")
            elif not self.storage_auto_resize['enabled'] and actual_settings['storageAutoResize']:
                raise Exception(f"illegal config: currently it's impossible to switch off storage auto-resizing "
                                f"(Google APIs seem to reject this change)")
            elif self.storage_auto_resize['enabled'] != actual_settings['storageAutoResize']:
                raise Exception(f"illegal config: currently it's impossible to switch ")
            elif 'limit' in self.storage_auto_resize \
                    and self.storage_auto_resize['limit'] != int(actual_settings['storageAutoResizeLimit']):
                actions.append(DAction(name='update-storage-auto-resize',
                                       description=f"Update SQL instance storage auto-resizing"))

        # validate labels
        if self.labels is not None:
            actual_labels: dict = actual_settings['userLabels'] if 'userLabels' in actual_settings else {}
            for key, value in self.labels.items():
                if key not in actual_labels or value != actual_labels[key]:
                    actions.append(DAction(name='update-labels', description=f"Update SQL instance user-labels"))
                    break

        # TODO: support data initializer scripts (for each script attach "conditions" that decide if they should run)

        return actions

    @action
    def enable_sqladmin_api(self, args):
        if args: pass
        for api in ['sqladmin.googleapis.com', 'sql-component.googleapis.com']:
            wait_for_service_manager_operation(
                get_service_management().services().enable(serviceName=api, body={
                    'consumerId': f"project:{self.project.project_id}"
                }).execute()
            )

            # poll until actually enabled
            timeout = 60
            interval = 3
            waited = 0
            while waited < timeout and api not in get_project_enabled_apis(project_id=self.project.project_id):
                time.sleep(interval)
                waited += interval
            if waited >= interval:
                raise Exception(f"Timed out while waiting for SQL Admin API to enable.")

    @action
    def create_sql_instance(self, args) -> None:
        if args: pass
        body = {
            "name": self.name,
            "settings": {
                "tier": self.machine_type,  # https://cloud.google.com/sql/pricing#2nd-gen-instance-pricing
                "dataDiskSizeGb": self.data_disk_size_gb or 10,
                "dataDiskType": self.data_disk_type or "PD_SSD",
                "databaseFlags": self.flags or [],
                "ipConfiguration": {
                    "requireSsl": self.require_ssl if self.require_ssl is not None else False,
                    "authorizedNetworks": self.authorized_networks or [],
                },
                "locationPreference": {
                    "zone": self.zone,
                },
                "maintenanceWindow": self.maintenance_window or {"day": 7, "hour": 3},
                "pricingPlan": "PER_USE",
                "userLabels": self.labels or {}
            },
            "databaseVersion": "MYSQL_5_7",
            # "failoverReplica": {
            #     "name": self.name + '-failover',
            # },
            "region": region_from_zone(self.zone),
            # "replicaConfiguration": {
            #     "failoverTarget": True,
            # }
        }
        settings = body['settings']

        # apply backup information
        if self.backup is not None:
            settings['backupConfiguration'] = {
                'enabled': self.backup['enabled'],
                'binaryLogEnabled': self.backup['enabled']
            }
            if self.backup['enabled'] and 'time' in self.backup:
                settings['backupConfiguration']['startTime'] = self.backup['time']

        # apply storage auto-resize
        if self.storage_auto_resize is not None:
            settings['storageAutoResize'] = self.storage_auto_resize['enabled']
            if self.storage_auto_resize['enabled'] and 'limit' in self.storage_auto_resize:
                settings['storageAutoResizeLimit'] = self.storage_auto_resize['limit']

        op = get_sql().instances().insert(project=self.project.project_id, body=body).execute()
        wait_for_sql_operation(self.project.project_id, op)

    @action
    def update_zone(self, args) -> None:
        if args: pass
        op = get_sql().instances().patch(project=self.project.project_id, instance=self.name, body={
            'settings': {
                'locationPreference': {
                    'zone': self.zone
                }
            }
        }).execute()
        wait_for_sql_operation(project_id=self.project.project_id, operation=op)

    @action
    def update_machine_type(self, args) -> None:
        if args: pass
        op = get_sql().instances().patch(project=self.project.project_id, instance=self.name, body={
            'settings': {
                'tier': self.machine_type
            }
        }).execute()
        wait_for_sql_operation(project_id=self.project.project_id, operation=op)

    @action
    def update_backup(self, args) -> None:
        if args: pass
        body = {
            'settings': {
                'backupConfiguration': {
                    'enabled': self.backup['enabled'],
                    'binaryLogEnabled': self.backup['enabled']
                }
            }
        }
        if self.backup['enabled'] and 'time' in self.backup:
            body['settings']['backupConfiguration']['startTime'] = self.backup['time']
        op = get_sql().instances().patch(project=self.project.project_id, instance=self.name, body=body).execute()
        wait_for_sql_operation(project_id=self.project.project_id, operation=op)

    @action
    def update_data_disk_size(self, args) -> None:
        if args: pass
        body = {
            'settings': {
                'dataDiskSizeGb': str(self.data_disk_size_gb)
            }
        }
        op = get_sql().instances().patch(project=self.project.project_id, instance=self.name, body=body).execute()
        wait_for_sql_operation(project_id=self.project.project_id, operation=op)

    @action
    def update_data_disk_type(self, args) -> None:
        if args: pass
        body = {
            'settings': {
                'dataDiskType': self.data_disk_type
            }
        }
        op = get_sql().instances().patch(project=self.project.project_id, instance=self.name, body=body).execute()
        wait_for_sql_operation(project_id=self.project.project_id, operation=op)

    @action
    def update_flags(self, args) -> None:
        if args: pass
        body = {
            'settings': {
                'databaseFlags': self.flags
            }
        }
        op = get_sql().instances().patch(project=self.project.project_id, instance=self.name, body=body).execute()
        wait_for_sql_operation(project_id=self.project.project_id, operation=op)

    @action
    def update_require_ssl(self, args) -> None:
        if args: pass
        body = {
            'settings': {
                'ipConfiguration': {
                    'requireSsl': self.require_ssl
                }
            }
        }
        op = get_sql().instances().patch(project=self.project.project_id, instance=self.name, body=body).execute()
        wait_for_sql_operation(project_id=self.project.project_id, operation=op)

    @action
    def update_authorized_networks(self, args) -> None:
        if args: pass
        body = {
            'settings': {
                'ipConfiguration': {
                    'authorizedNetworks': self.authorized_networks
                }
            }
        }
        op = get_sql().instances().patch(project=self.project.project_id, instance=self.name, body=body).execute()
        wait_for_sql_operation(project_id=self.project.project_id, operation=op)

    @action
    def update_maintenance_window(self, args) -> None:
        if args: pass
        body = {
            'settings': {
                'maintenanceWindow': self.maintenance_window
            }
        }
        op = get_sql().instances().patch(project=self.project.project_id, instance=self.name, body=body).execute()
        wait_for_sql_operation(project_id=self.project.project_id, operation=op)

    @action
    def update_storage_auto_resize(self, args) -> None:
        if args: pass
        body = {
            'settings': {
                'storageAutoResize': self.storage_auto_resize['enabled']
            }
        }
        if self.storage_auto_resize['enabled']:
            body['settings']['storageAutoResizeLimit'] = self.storage_auto_resize['limit']
        op = get_sql().instances().patch(project=self.project.project_id, instance=self.name, body=body).execute()
        wait_for_sql_operation(project_id=self.project.project_id, operation=op)

    @action
    def update_labels(self, args) -> None:
        if args: pass
        # TODO: currently, this DOES NOT remove old labels, just adds new ones and updates existing ones
        body = {
            'settings': {
                'userLabels': self.labels
            }
        }
        op = get_sql().instances().patch(project=self.project.project_id, instance=self.name, body=body).execute()
        wait_for_sql_operation(project_id=self.project.project_id, operation=op)


def main():
    GcpCloudSql(json.loads(sys.stdin.read())).execute()


if __name__ == "__main__":
    main()
