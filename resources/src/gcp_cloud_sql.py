#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from copy import deepcopy
from pprint import pprint
from typing import Mapping, Sequence, MutableSequence

import pymysql
from googleapiclient.errors import HttpError
from pymysql.connections import Connection

from dresources import DAction, action
from gcp import GcpResource
from gcp_project import GcpProject
from gcp_services import get_sql, region_from_zone, wait_for_sql_operation, get_project_enabled_apis, \
    get_service_management, wait_for_service_manager_operation


class Condition(ABC):

    def __init__(self, condition_factory, data: dict) -> None:
        super().__init__()
        self._condition_factory: ConditionFactory = condition_factory
        self._data = data

    @property
    def condition_factory(self):
        return self._condition_factory

    @property
    def data(self) -> dict:
        return self._data

    @abstractmethod
    def evaluate(self, connection: Connection) -> bool:
        raise Exception(f"not implemented")


class AnyMissingSchemaCondition(Condition):

    @staticmethod
    def config_schema() -> dict:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["if", "schemas"],
            "properties": {
                "if": {
                    "type": "string",
                    "pattern": "^ANY_SCHEMA_MISSING$"
                },
                "schemas": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string"}
                }
            }
        }

    def __init__(self, condition_factory, data: dict) -> None:
        super().__init__(condition_factory, data)

    def evaluate(self, connection: Connection) -> bool:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT SCHEMA_NAME FROM SCHEMATA")
            existing_schemas = [row['SCHEMA_NAME'] for row in cursor.fetchall()]
            required_schemas = self._data['schemas']
            missing_schemas = [schema for schema in required_schemas if schema not in existing_schemas]
            return True if missing_schemas else False


class AnyMissingTableCondition(Condition):

    @staticmethod
    def config_schema() -> dict:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["if", "tables"],
            "properties": {
                "if": {
                    "type": "string",
                    "pattern": "^ANY_TABLE_MISSING$"
                },
                "tables": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "string",
                        "pattern": "^.+\\..+$"
                    }
                }
            }
        }

    def __init__(self, condition_factory, data: dict) -> None:
        super().__init__(condition_factory, data)

    def evaluate(self, connection: Connection) -> bool:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT TABLE_NAME, TABLE_SCHEMA, TABLE_CATALOG FROM information_schema.TABLES")
            existing_tables = [f"{row['TABLE_SCHEMA']}.{row['TABLE_NAME']}" for row in cursor.fetchall()]
            required_tables = self._data['tables']
            missing_tables = [table for table in required_tables if table not in existing_tables]
            return True if missing_tables else False


class NoSchemaMissingCondition(Condition):

    @staticmethod
    def config_schema() -> dict:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["if", "schemas"],
            "properties": {
                "if": {
                    "type": "string",
                    "pattern": "^NO_SCHEMA_MISSING$"
                },
                "schemas": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string"}
                }
            }
        }

    def __init__(self, condition_factory, data: dict) -> None:
        super().__init__(condition_factory, data)

    def evaluate(self, connection: Connection) -> bool:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT SCHEMA_NAME FROM SCHEMATA")
            existing_schema_names = [row['SCHEMA_NAME'] for row in cursor.fetchall()]
            required_schemas = self._data['schemas']
            missing_schema_names = [required_schema
                                    for required_schema in required_schemas
                                    if required_schema not in existing_schema_names]
            return False if missing_schema_names else True


class NoTableMissingCondition(Condition):

    @staticmethod
    def config_schema() -> dict:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["if", "tables"],
            "properties": {
                "if": {
                    "type": "string",
                    "pattern": "^NO_TABLE_MISSING$"
                },
                "tables": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "string",
                        "pattern": "^.+\\..+$"
                    }
                }
            }
        }

    def __init__(self, condition_factory, data: dict) -> None:
        super().__init__(condition_factory, data)

    def evaluate(self, connection: Connection) -> bool:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT TABLE_NAME, TABLE_SCHEMA, TABLE_CATALOG FROM information_schema.TABLES")
            existing_tables = [f"{row['TABLE_SCHEMA']}.{row['TABLE_NAME']}" for row in cursor.fetchall()]
            required_tables = self._data['tables']
            missing_tables = [table for table in required_tables if table not in existing_tables]
            return False if missing_tables else True


class ExpectedRowCountCondition(Condition):

    @staticmethod
    def config_schema() -> dict:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["if", "sql", "rows-expected"],
            "properties": {
                "if": {
                    "type": "string",
                    "pattern": "^EXPECTED_ROW_COUNT$"
                },
                "sql": {
                    "type": "string"
                },
                "rows-expected": {
                    "type": "integer",
                    "minimum": 0
                }
            }
        }

    def __init__(self, condition_factory, data: dict) -> None:
        super().__init__(condition_factory, data)

    def evaluate(self, connection: Connection) -> bool:
        with connection.cursor() as cursor:
            cursor.execute(self.data['sql'])
            row_count = len([row for row in cursor.fetchall()])
            return row_count == self.data['rows-expected']


class AllCondition(Condition):

    @staticmethod
    def config_schema() -> dict:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["if", "conditions"],
            "properties": {
                "if": {
                    "type": "string",
                    "pattern": "^ALL$"
                },
                "conditions": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "$ref": "#/definitions/CONDITION"
                    }
                }
            }
        }

    def __init__(self, condition_factory, data: dict) -> None:
        super().__init__(condition_factory, data)

    def evaluate(self, connection: Connection) -> bool:
        for condition_data in self.data['conditions']:
            condition = self.condition_factory.create_condition(condition_data)
            if not condition.evaluate(connection):
                return False
        return True


class AnyCondition(Condition):

    @staticmethod
    def config_schema() -> dict:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["if", "conditions"],
            "properties": {
                "if": {
                    "type": "string",
                    "pattern": "^ANY$"
                },
                "conditions": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "$ref": "#/definitions/CONDITION"
                    }
                }
            }
        }

    def __init__(self, condition_factory, data: dict) -> None:
        super().__init__(condition_factory, data)

    def evaluate(self, connection: Connection) -> bool:
        for condition_data in self.data['conditions']:
            condition = self.condition_factory.create_condition(condition_data)
            if condition.evaluate(connection):
                return True
        return False


CONDITION_TYPES = {
    'ANY_SCHEMA_MISSING': AnyMissingSchemaCondition,
    'ANY_TABLE_MISSING': AnyMissingTableCondition,
    'NO_SCHEMA_MISSING': NoSchemaMissingCondition,
    'NO_TABLE_MISSING': NoTableMissingCondition,
    'EXPECTED_ROW_COUNT': ExpectedRowCountCondition,
    'ALL': AllCondition,
    'ANY': AnyCondition
}


class ConditionFactory:

    def __init__(self) -> None:
        super().__init__()

    def create_condition(self, data: dict) -> Condition:
        if 'if' not in data:
            raise Exception(f"illegal config: missing 'if' property in {json.dumps(data)}")
        condition_type = data['if']
        if condition_type in CONDITION_TYPES:
            return CONDITION_TYPES[condition_type](self, data)
        else:
            raise Exception(f"illegal config: unsupported condition '{condition_type}'. Available conditions "
                            f"are: {CONDITION_TYPES.keys()}")

    def create_conditions(self, conditions_data: Sequence[dict]) -> Sequence[Condition]:
        return [self.create_condition(cdata) for cdata in conditions_data]


class Script:

    def __init__(self, name: str, paths: Sequence[str], conditions: Sequence[Condition]) -> None:
        super().__init__()
        self._name = name
        self._paths: Sequence[str] = paths
        self._conditions: Sequence[Condition] = conditions

    @property
    def name(self) -> str:
        return self._name

    @property
    def paths(self) -> Sequence[str]:
        return self._paths

    @property
    def conditions(self) -> Sequence[Condition]:
        return self._conditions

    def should_execute(self, connection: Connection) -> bool:
        if len(self._conditions) == 0:
            return True

        for condition in self._conditions:
            if condition.evaluate(connection=connection):
                return True
        return False

    def execute(self, username: str, password: str) -> None:
        for path in self._paths:
            command = \
                f"/usr/bin/mysql --user={username} --password={password} --host=127.0.0.1 information_schema < {path}"
            subprocess.run(command, shell=True, check=True)


class ScriptEvaluator:

    def __init__(self, sql_resource) -> None:
        super().__init__()
        self._project_id: str = sql_resource.project.project_id
        self._region: str = sql_resource.region
        self._instance: str = sql_resource.name
        self._db_username: str = 'root'
        self._db_password: str = sql_resource.root_password
        self._proxy_process: subprocess.Popen = None
        self._connection: Connection = None

        condition_factory: ConditionFactory = ConditionFactory()
        self._scripts: Sequence[Script] = \
            [Script(name=data['name'],
                    paths=data['paths'],
                    conditions=condition_factory.create_conditions(data['when']))
             for data in sql_resource.scripts]

    @property
    def scripts(self) -> Sequence[Script]:
        return self._scripts

    def get_script(self, name: str) -> Script:
        return next(script for script in self.scripts if script.name == name)

    def get_scripts_to_execute(self) -> Sequence[Script]:
        if self._connection is None:
            raise Exception(
                f"illegal state: connection not available (did you invoke ScriptEvaluator outside 'with' context?)")
        else:
            return [script for script in self._scripts if script.should_execute(self._connection)]

    def execute_scripts(self, scripts: Sequence[Script]) -> None:
        if self._connection is None:
            raise Exception(
                f"illegal state: connection not available (did you invoke ScriptEvaluator outside 'with' context?)")
        else:
            for script in scripts:
                script.execute(username=self._db_username, password=self._db_password)

    def __enter__(self):

        op = get_sql().users().update(project=self._project_id, instance=self._instance, host='%', name='root', body={
            'password': self._db_password
        }).execute()
        wait_for_sql_operation(project_id=self._project_id, operation=op)

        self._proxy_process: subprocess.Popen = \
            subprocess.Popen([f'/usr/local/bin/cloud_sql_proxy',
                              f'-instances={self._project_id}:{self._region}:{self._instance}=tcp:3306',
                              f'-credential_file=/deployster/service-account.json'])
        try:
            self._proxy_process.wait(2)
            raise Exception(f"could not start Cloud SQL Proxy!")
        except subprocess.TimeoutExpired:
            pass

        print(f"Connecting to MySQL...", file=sys.stderr)
        self._connection: Connection = pymysql.connect(host='localhost',
                                                       port=3306,
                                                       user=self._db_username,
                                                       password=self._db_password,
                                                       db='INFORMATION_SCHEMA',
                                                       charset='utf8mb4',
                                                       cursorclass=pymysql.cursors.DictCursor)
        return self

    def __exit__(self, *exc):
        try:
            self._connection.close()
        finally:
            self._proxy_process.terminate()


class GcpCloudSql(GcpResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.add_dependency(name='project', type='infolinks/deployster-gcp-project', optional=False, factory=GcpProject)

        # build definitions for condition types
        condition_definitions = {}
        for alias, factory in CONDITION_TYPES.items():
            condition_definitions[alias] = factory.config_schema()
        condition_definitions['CONDITION'] = {
            "oneOf": [{"$ref": f"#/definitions/{alias}"} for alias in condition_definitions.keys()]
        }

        # build full list of all definitions
        definitions = {}
        definitions.update(condition_definitions)

        # create the configuration schema
        self.config_schema.update({
            "type": "object",
            "required": ["zone", "name", "machine-type", "root-password"],
            "additionalProperties": False,
            "definitions": definitions,
            "properties": {
                "zone": {"type": "string"},
                "name": {"type": "string"},
                "machine-type": {"type": "string"},
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
                },
                "root-password": {
                    "type": "string",
                    "pattern": ".+"
                },
                "scripts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["name", "paths", "when"],
                        "properties": {
                            "name": {"type": "string"},
                            "paths": {
                                "type": "array",
                                "minItems": 1,
                                "uniqueItems": True,
                                "items": {"type": "string"}
                            },
                            "when": {
                                "type": "array",
                                "minItems": 1,
                                "items": {"$ref": "#/definitions/CONDITION"}
                            }
                        }
                    }
                }
            }
        })
        pprint(self.config_schema, stream=sys.stderr)

    @property
    def project(self) -> GcpProject:
        return self.get_dependency('project')

    @property
    def zone(self) -> str:
        return self.resource_config['zone']

    @property
    def region(self) -> str:
        return region_from_zone(self.zone)

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
                    raise Exception(f"illegal config: unknown maintenance day encountered: {maintenance['day']}")
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

    @property
    def scripts(self) -> Sequence[dict]:
        return self.resource_config['scripts'] if 'scripts' in self.resource_config else None

    @property
    def root_password(self) -> str:
        return self.resource_config['root-password'] if 'root-password' in self.resource_config else None

    def discover_actual_properties(self):
        sql = get_sql()
        allowed_tiers = \
            {tier['tier']: tier
             for tier in sql.tiers().list(project=self.project.project_id).execute()['items']
             if tier['tier'].startswith('db-')}
        allowed_flags = \
            {flag['name']: flag for flag in sql.flags().list(databaseVersion='MYSQL_5_7').execute()['items']}
        for desired_flag in self.flags:
            desired_name = desired_flag['name']
            if desired_name not in allowed_flags:
                raise Exception(f"illegal config: flag '{desired_name}' is not a supported MySQL 5.7 flag.")

            allowed_flag = allowed_flags[desired_name]
            flag_type = allowed_flag['type']
            if flag_type == 'NONE':
                if 'value' in desired_flag:
                    raise Exception(f"illegal config: flag '{desired_name}' does not accept values.")

            elif flag_type == 'INTEGER':
                if 'value' not in desired_flag:
                    raise Exception(f"illegal config: flag '{desired_name}' requires a value.")
                try:
                    int_value = int(desired_flag['value'])
                except ValueError as e:
                    raise Exception(f"illegal config: flag '{desired_name}' value must be an integer") from e

                if 'minValue' in allowed_flag and int_value < int(allowed_flag['minValue']):
                    min_value = allowed_flag['minValue']
                    raise Exception(f"illegal config: flag '{desired_name}' value must be greater than {min_value}")
                if 'maxValue' in allowed_flag and int_value > int(allowed_flag['maxValue']):
                    max_value = allowed_flag['maxValue']
                    raise Exception(f"illegal config: flag '{desired_name}' value must not be greater than {max_value}")

            elif flag_type == 'STRING':
                if 'value' not in desired_flag:
                    raise Exception(f"illegal config: flag '{desired_name}' requires a value.")
                elif 'allowedStringValues' in allowed_flag:
                    allowed_values = allowed_flag['allowedStringValues']
                    if desired_flag['value'] not in allowed_values:
                        raise Exception(f"illegal config: flag '{desired_name}' value must be one of: {allowed_values}")

            elif flag_type == 'BOOLEAN':
                if 'value' not in desired_flag:
                    raise Exception(f"illegal config: flag '{desired_name}' requires a value.")
                elif desired_flag['value'] not in ['yes', 'no']:
                    raise Exception(f"illegal config: flag '{desired_name}' value must be 'on' or 'off'.")

        # validate machine-type against allowed tiers (tier=machine-type in Cloud SQL lingo)
        desired_tier = self.machine_type
        if desired_tier not in allowed_tiers:
            raise Exception(f"illegal config: unsupported")
        tier = allowed_tiers[desired_tier]
        if self.region not in tier['region']:
            raise Exception(f"illegal config: machine-type '{desired_tier}' is not supported in "
                            f"region '{self.region}'")

        # validate all paths in given scripts exist
        for script in self.scripts:
            for path in script['paths']:
                if not os.path.exists(path):
                    raise Exception(f"illegal config: could not find script '{path}'")

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

        # no need to evaluate scripts, since instance does not yet exist; the create action will do it once it creates
        # the instance successfully

        return actions

    def get_actions_when_existing(self, actual_properties: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = []
        actual = actual_properties
        actual_settings = actual['settings']

        # validate instance is RUNNING
        if actual['state'] != "RUNNABLE":
            raise Exception(f"illegal state: instance exists, but not running ('{actual['state']}')")

        # validate instance region
        if actual['region'] != self.region:
            raise Exception(
                f"illegal config: SQL instance is in region '{actual['region']}' instead of '{self.region}'. "
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

        # check for scripts that need to be executed
        if self.scripts:
            with ScriptEvaluator(sql_resource=self) as evaluator:
                for script in evaluator.get_scripts_to_execute():
                    actions.append(
                        DAction(name='execute-script',
                                description=f"Execute '{script.name}' SQL scripts",
                                args=['execute_scripts', script.name]))

        return actions

    def define_action_args(self, action: str, argparser: argparse.ArgumentParser):
        super().define_action_args(action, argparser)
        if action == 'execute_scripts':
            argparser.add_argument('scripts', nargs='+')

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
                raise Exception(f"illegal state: Timed out while waiting for SQL Admin API to enable.")

    @action
    def create_sql_instance(self, args) -> None:
        if args: pass
        body = {
            "name": self.name,
            "settings": {
                "tier": self.machine_type,  # https://cloud.google.com/sql/pricing#2nd-gen-instance-pricing
                "dataDiskSizeGb": str(self.data_disk_size_gb or 10),
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
            "region": self.region,
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
                settings['storageAutoResizeLimit'] = str(self.storage_auto_resize['limit'])

        # create instance
        try:
            op = get_sql().instances().insert(project=self.project.project_id, body=body).execute()
            wait_for_sql_operation(self.project.project_id, op)
        except HttpError as e:
            status = e.resp.status
            if status == 409:
                raise Exception(f"failed creating SQL instance, possibly due to instance name reuse (you can't "
                                f"reuse an instance name for a week after its deletion)") from e

        # set 'root' password
        op = get_sql().users().update(project=self.project.project_id, instance=self.name, host='%', body={
            'name': 'root',
            'password': self.root_password
        }).execute()
        wait_for_sql_operation(project_id=self.project.project_id, operation=op)

        # check for scripts that need to be executed
        if self.scripts:
            with ScriptEvaluator(sql_resource=self) as evaluator:
                evaluator.execute_scripts(scripts=evaluator.get_scripts_to_execute())

    @action
    def execute_scripts(self, args) -> None:
        with ScriptEvaluator(sql_resource=self) as evaluator:
            scripts: Sequence[Script] = [evaluator.get_script(script_name) for script_name in args.scripts]
            evaluator.execute_scripts(scripts=scripts)

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
