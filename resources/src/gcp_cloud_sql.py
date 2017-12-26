#!/usr/bin/env python3.6

import argparse
import json
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from pprint import pformat
from typing import Sequence, MutableSequence, Any, Mapping

from jinja2 import Environment, Template

from dresources import DAction, action
from external_services import ExternalServices
from external_services import region_from_zone, SqlExecutor
from gcp import GcpResource


def _translate_day_name_to_number(day_name: str) -> int:
    if day_name == 'Monday':
        return 1
    elif day_name == 'Tuesday':
        return 2
    elif day_name == 'Wednesday':
        return 3
    elif day_name == 'Thursday':
        return 4
    elif day_name == 'Friday':
        return 5
    elif day_name == 'Saturday':
        return 6
    elif day_name == 'Sunday':
        return 7
    else:
        raise Exception(f"illegal config: unknown week-day encountered: {day_name}")


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
    def evaluate(self, sql_executor: SqlExecutor) -> bool:
        raise NotImplementedError(f"not implemented")


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

    def evaluate(self, sql_executor: SqlExecutor) -> bool:
        existing_schemas = [row["SCHEMA_NAME"]
                            for row in sql_executor.execute_sql(f"SELECT SCHEMA_NAME "
                                                                f"FROM information_schema.SCHEMATA")]
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

    def evaluate(self, sql_executor: SqlExecutor) -> bool:
        sql: str = f"SELECT TABLE_SCHEMA, TABLE_NAME FROM information_schema.TABLES"
        existing_tables = [f"{row['TABLE_SCHEMA']}.{row['TABLE_NAME']}" for row in sql_executor.execute_sql(sql)]
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

    def evaluate(self, sql_executor: SqlExecutor) -> bool:
        sql: str = f"SELECT SCHEMA_NAME FROM information_schema.SCHEMATA"
        existing_schema_names = [row['SCHEMA_NAME'] for row in sql_executor.execute_sql(sql)]
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

    def evaluate(self, sql_executor: SqlExecutor) -> bool:
        sql: str = f"SELECT TABLE_SCHEMA, TABLE_NAME FROM information_schema.TABLES"
        existing_tables = [f"{row['TABLE_SCHEMA']}.{row['TABLE_NAME']}" for row in sql_executor.execute_sql(sql)]
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

    def evaluate(self, sql_executor: SqlExecutor) -> bool:
        row_count = len([row for row in sql_executor.execute_sql(self.data['sql'])])
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

    def evaluate(self, sql_executor: SqlExecutor) -> bool:
        for condition_data in self.data['conditions']:
            condition = self.condition_factory.create_condition(condition_data)
            if not condition.evaluate(sql_executor=sql_executor):
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

    def evaluate(self, sql_executor: SqlExecutor) -> bool:
        for condition_data in self.data['conditions']:
            condition = self.condition_factory.create_condition(condition_data)
            if condition.evaluate(sql_executor=sql_executor):
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
        condition_type = data['if']
        return CONDITION_TYPES[condition_type](self, data)

    def create_conditions(self, conditions_data: Sequence[dict]) -> Sequence[Condition]:
        return [self.create_condition(cdata) for cdata in conditions_data]


class ScriptFile:

    def __init__(self, path: str, post_process: bool = False, context: Mapping[str, Any] = None) -> None:
        super().__init__()
        self._path: Path = Path(path).absolute()
        self._post_process: bool = post_process
        self._context = context

    @property
    def path(self) -> Path:
        return self._path

    def execute(self, sql_executor: SqlExecutor) -> None:
        if self._post_process:
            escaped_file: Path = Path('/tmp') / self._path.name
            template: Template = Environment().from_string(open(self._path, 'r').read(), globals=self._context)
            with escaped_file.open(mode='w') as f:
                f.write(template.render(self._context))
            sql_executor.execute_sql_script(path=str(escaped_file))
        else:
            sql_executor.execute_sql_script(path=str(self._path))


class Script:

    def __init__(self,
                 name: str,
                 paths: Sequence[Any],
                 conditions: Sequence[Condition],
                 context: Mapping[str, Any]) -> None:
        super().__init__()
        self._name = name

        script_files: MutableSequence[ScriptFile] = []
        for path in paths:
            if isinstance(path, str):
                script_files.append(ScriptFile(path=path))
            elif isinstance(path, dict):
                if 'post_process' in path:
                    script_files.append(ScriptFile(path=path['path'],
                                                   post_process=path['post_process'],
                                                   context=context))
                else:
                    script_files.append(ScriptFile(path=path['path']))
            else:
                raise Exception(f"illegal config: unsupport path object: {pformat(path)}")  # pragma: no cover
        self._script_files: Sequence[ScriptFile] = script_files
        self._conditions: Sequence[Condition] = conditions

    @property
    def name(self) -> str:
        return self._name

    def should_execute(self, sql_executor: SqlExecutor) -> bool:
        for file in self._script_files:
            if not file.path.exists():
                raise Exception(f"illegal state: SQL script '{file.path}' could not be found")

        if len(self._conditions) == 0:
            return True

        for condition in self._conditions:
            if condition.evaluate(sql_executor=sql_executor):
                return True
        return False

    def execute(self, sql_executor: SqlExecutor) -> None:
        for file in self._script_files:
            file.execute(sql_executor=sql_executor)


class ScriptEvaluator:

    def __init__(self,
                 svc: ExternalServices,
                 project_id: str,
                 instance_name: str,
                 root_password: str,
                 zone: str,
                 scripts_data: Sequence[dict],
                 context: Mapping[str, Any]) -> None:
        super().__init__()
        self._sql_executor: SqlExecutor = \
            svc.create_gcp_sql_executor(project_id=project_id,
                                        instance=instance_name,
                                        password=root_password,
                                        region=region_from_zone(zone=zone))

        condition_factory: ConditionFactory = ConditionFactory()
        self._scripts: Sequence[Script] = \
            [Script(name=data['name'],
                    paths=data['paths'],
                    conditions=condition_factory.create_conditions(data['when']),
                    context=context)
             for data in scripts_data]

    def get_script(self, name: str) -> Script:
        return next(script for script in self._scripts if script.name == name)

    def get_scripts_to_execute(self) -> Sequence[Script]:
        return [script for script in self._scripts if script.should_execute(self._sql_executor)]

    def execute_scripts(self, scripts: Sequence[Script]) -> None:
        for script in scripts:
            script.execute(sql_executor=self._sql_executor)

    def __enter__(self):
        self._sql_executor.open()
        return self

    def __exit__(self, *exc):
        self._sql_executor.close()


class GcpCloudSql(GcpResource):

    def __init__(self, data: dict, svc: ExternalServices = ExternalServices()) -> None:
        super().__init__(data=data, svc=svc)

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
                "project_id": {"type": "string"},
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
                    "oneOf": [
                        {"type": "null"},
                        {
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
                        }
                    ]
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
                "users": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "name": {"type": "string", "minLength": 1},
                            "password": {"type": "string", "minLength": 5}
                        }
                    }
                },
                "scripts_ctx": {"type": "object"},
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
                                "items": {
                                    "oneOf": [
                                        {"type": "string"},
                                        {
                                            "type": "object",
                                            "required": ["path"],
                                            "additionalProperties": False,
                                            "properties": {
                                                "path": {"type": "string"},
                                                "post_process": {"type": "boolean"}
                                            }
                                        }
                                    ]
                                }
                            },
                            "when": {
                                "type": "array",
                                "items": {"$ref": "#/definitions/CONDITION"}
                            }
                        }
                    }
                }
            }
        })

        # translate maintenance window name to number
        if self.info.has_config:
            cfg: dict = self.info.config
            if "maintenance" in cfg and cfg["maintenance"] is not None:
                if 'day' in cfg["maintenance"] and type(cfg["maintenance"]['day']) == str:
                    cfg["maintenance"]['day'] = _translate_day_name_to_number(cfg["maintenance"]['day'])

    def discover_state(self):
        cfg: dict = self.info.config

        if 'flags' in cfg:
            allowed_flags: dict = self.svc.get_gcp_sql_allowed_flags()
            for desired_flag in cfg['flags']:
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
                        raise Exception(
                            f"illegal config: flag '{desired_name}' value must not be greater than {max_value}")

                elif flag_type == 'STRING':
                    if 'value' not in desired_flag:
                        raise Exception(f"illegal config: flag '{desired_name}' requires a value.")
                    elif 'allowedStringValues' in allowed_flag:
                        allowed_values = allowed_flag['allowedStringValues']
                        if desired_flag['value'] not in allowed_values:
                            raise Exception(
                                f"illegal config: flag '{desired_name}' value must be one of: {allowed_values}")

                elif flag_type == 'BOOLEAN':
                    if 'value' not in desired_flag:
                        raise Exception(f"illegal config: flag '{desired_name}' requires a value.")
                    elif desired_flag['value'] not in ['on', 'off']:
                        raise Exception(f"illegal config: flag '{desired_name}' value must be 'on' or 'off'.")

                else:
                    raise Exception(
                        f"illegal state: unsupported flag type ('{flag_type}') found for flag '{desired_name}'")

        # validate machine-type against allowed tiers (tier=machine-type in Cloud SQL lingo)
        allowed_tiers: dict = self.svc.get_gcp_sql_allowed_tiers(project_id=self.info.config['project_id'])
        desired_tier = cfg["machine-type"]
        if desired_tier not in allowed_tiers:
            raise Exception(f"illegal config: unsupported machine_type '{desired_tier}'")
        tier = allowed_tiers[desired_tier]
        region = region_from_zone(cfg['zone'])
        if region not in tier['region']:
            raise Exception(f"illegal config: machine-type '{desired_tier}' is not supported in region '{region}'")

        # if the SQL Admin API is not enabled, there can be no SQL instances
        enabled_apis = self.svc.find_gcp_project_enabled_apis(project_id=cfg['project_id'])
        if enabled_apis is not None:
            if 'sqladmin.googleapis.com' in enabled_apis and 'sql-component.googleapis.com' in enabled_apis:
                instance = self.svc.get_gcp_sql_instance(project_id=cfg['project_id'], instance_name=cfg['name'])
                if instance:
                    if 'users' in self.info.config:
                        instance['users'] = \
                            self.svc.get_gcp_sql_users(project_id=cfg['project_id'], instance_name=cfg['name'])
                    else:
                        instance['users'] = []
                return instance
        return None

    def get_actions_for_missing_state(self) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = []
        cfg: dict = self.info.config

        enabled_apis = self.svc.find_gcp_project_enabled_apis(project_id=cfg['project_id'])
        if enabled_apis is None \
                or 'sqladmin.googleapis.com' not in enabled_apis \
                or 'sql-component.googleapis.com' not in enabled_apis:
            # if the SQL Admin API is not enabled, there can be no SQL instances; we will, however, have to enable
            # that API for the project later on.
            actions.append(DAction(name='enable-sql-apis',
                                   description=f"Enable Cloud SQL APIs for project '{cfg['project_id']}'"))

        actions.append(DAction(name=f"create-sql-instance", description=f"Create SQL instance '{cfg['name']}'"))

        # no need to evaluate scripts, since instance does not yet exist; the create action will do it once it creates
        # the instance successfully

        return actions

    def get_actions_for_discovered_state(self, state: dict) -> Sequence[DAction]:
        actions: MutableSequence[DAction] = []
        actual = state
        actual_settings = actual['settings']
        cfg = self.info.config

        # validate instance is RUNNING
        if actual['state'] != "RUNNABLE":
            raise Exception(f"illegal state: instance exists, but not running ('{actual['state']}')")

        # validate instance region
        zone = cfg['zone']
        region = region_from_zone(zone)
        if actual['region'] != region:
            raise Exception(
                f"illegal config: SQL instance is in region '{actual['region']}' instead of '{region}'. "
                f"Unfortunately, changing SQL instances regions is not allowed in Google Cloud SQL.")

        # validate instance preferred zone
        if actual_settings['locationPreference']['zone'] != zone:
            actions.append(DAction(name='update-zone',
                                   description=f"Update SQL instance preferred zone to '{zone}'"))

        # validate instance machine type
        machine_type = cfg['machine-type']
        if actual_settings['tier'] != machine_type:
            actions.append(DAction(name='update-machine-type',
                                   description=f"Update SQL instance machine type to '{machine_type}'"))

        # validate backup configuration
        if 'backup' in cfg:
            desired_backup: dict = cfg['backup']
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

        # validate data-disk size
        if "data-disk-size-gb" in cfg:
            desired_data_disk_size_gb: int = cfg["data-disk-size-gb"]
            actual_disk_size: int = int(actual_settings['dataDiskSizeGb'])
            if actual_disk_size != desired_data_disk_size_gb:
                if desired_data_disk_size_gb < actual_disk_size:
                    raise Exception(
                        f"illegal config: cannot reduce disk size from {actual_disk_size}gb to "
                        f"{desired_data_disk_size_gb}gb (not allowed by Cloud SQL APIs).")
                else:
                    actions.append(
                        DAction(name='update-data-disk-size',
                                description=f"Update SQL instance data disk size from {actual_disk_size}gb to "
                                            f"{desired_data_disk_size_gb}gb"))

        # validate data-disk type
        if "data-disk-type" in cfg:
            desired_data_disk_type: str = cfg["data-disk-type"]
            if actual_settings['dataDiskType'] != desired_data_disk_type:
                actions.append(DAction(name='update-data-disk-type',
                                       description=f"Update SQL instance data disk type to '{desired_data_disk_type}'"))

        # validate MySQL flags
        if 'flags' in cfg:
            desired_flags: dict = cfg['flags']
            actual_flags = actual_settings['databaseFlags'] if 'databaseFlags' in actual_settings else []
            if actual_flags != desired_flags:
                actions.append(DAction(name='update-flags', description=f"Update SQL instance flags"))

        # validate SSL connections requirement
        if "require-ssl" in cfg:
            desired_require_ssl: bool = cfg["require-ssl"]
            if actual_settings['ipConfiguration']['requireSsl'] != desired_require_ssl:
                actions.append(
                    DAction(name='update-require-ssl',
                            description=f"Update SQL instance to {'' if desired_require_ssl else 'not '}require "
                                        f"SSL connections"))

        # validate authorized networks
        if "authorized-networks" in cfg:
            desired_authorized_networks: list = cfg["authorized-networks"]

            # validate network names are unique
            names = set()
            for desired_network in desired_authorized_networks:
                if desired_network['name'] in names:
                    raise Exception(f"illegal config: network '{desired_network['name']}' defined more than once")
                else:
                    names.add(desired_network['name'])

            actual_auth_networks = actual_settings['ipConfiguration']['authorizedNetworks']
            if len(actual_auth_networks) != len(desired_authorized_networks):
                actions.append(
                    DAction(name='update-authorized-networks', description=f"Update SQL instance authorized networks"))
            else:
                # validate each network
                for desired_network in desired_authorized_networks:
                    try:
                        actual_network = next(n for n in actual_auth_networks if n['name'] == desired_network['name'])
                        desired_expiry = desired_network['expirationTime'] \
                            if 'expirationTime' in desired_network else None
                        actual_expiry = actual_network['expirationTime'] if 'expirationTime' in actual_network else None
                        if desired_network['value'] != actual_network['value'] or desired_expiry != actual_expiry:
                            actions.append(DAction(name='update-authorized-networks',
                                                   description=f"Update SQL instance authorized networks "
                                                               f"(found stale network: {desired_network['name']})"))
                            break
                    except StopIteration:
                        actions.append(DAction(name='update-authorized-networks',
                                               description=f"Update SQL instance authorized networks"))
                        break

        # validate maintenance window
        if "maintenance" in cfg:
            desired_maintenance: dict = cfg["maintenance"]
            actual_maintenance_window = actual_settings['maintenanceWindow']
            if desired_maintenance is None:
                actions.append(DAction(name='update-maintenance-window',
                                       description=f"Disable SQL instance maintenance window"))
            else:
                desired_day = desired_maintenance['day']
                desired_hour: int = desired_maintenance['hour']
                if desired_day != actual_maintenance_window['day'] or desired_hour != actual_maintenance_window['hour']:
                    actions.append(DAction(name='update-maintenance-window',
                                           description=f"Update SQL instance maintenance window"))

        # validate storage auto-resize
        if "storage-auto-resize" in cfg:
            desired_storage_auto_resize: dict = cfg["storage-auto-resize"]
            if not desired_storage_auto_resize['enabled'] and 'limit' in desired_storage_auto_resize:
                raise Exception(f"illegal config: cannot specify storage auto-resize limit when it's disabled")
            elif desired_storage_auto_resize['enabled'] != actual_settings['storageAutoResize']:
                raise Exception(f"illegal config: currently it's impossible to switch storage auto-resize "
                                f"(Google APIs seem to reject this change)")
            elif 'limit' in desired_storage_auto_resize \
                    and desired_storage_auto_resize['limit'] != int(actual_settings['storageAutoResizeLimit']):
                actions.append(DAction(name='update-storage-auto-resize',
                                       description=f"Update SQL instance storage auto-resizing"))

        # validate labels
        if "labels" in cfg:
            desired_labels: dict = cfg["labels"]
            actual_labels: dict = actual_settings['userLabels'] if 'userLabels' in actual_settings else {}
            if len(desired_labels.keys()) != len(actual_labels.keys()):
                actions.append(DAction(name='update-labels', description=f"Update SQL instance user-labels"))
            else:
                for key, value in desired_labels.items():
                    if key not in actual_labels or value != actual_labels[key]:
                        actions.append(DAction(name='update-labels', description=f"Update SQL instance user-labels"))
                        break

        # create missing users
        if 'users' in cfg:
            actual_users: list = actual['users']
            for user in cfg['users']:
                found: bool = False
                for actual_user in actual_users:
                    if user['name'] == actual_user['name']:
                        found: bool = True
                        break
                if not found:
                    actions.append(DAction(name='add-user',
                                           description=f"Create new user '{user['name']}'",
                                           args=["add_user", user['name']]))

        # check for scripts that need to be executed
        if "scripts" in cfg:
            evaluator: ScriptEvaluator = ScriptEvaluator(svc=self.svc,
                                                         project_id=cfg['project_id'],
                                                         instance_name=cfg['name'],
                                                         root_password=cfg['root-password'],
                                                         zone=zone,
                                                         scripts_data=self.info.config['scripts'],
                                                         context=cfg['scripts_ctx'] if 'scripts_ctx' in cfg else {})
            with evaluator as evaluator:
                for script in evaluator.get_scripts_to_execute():
                    actions.append(
                        DAction(name='execute-script',
                                description=f"Execute '{script.name}' SQL scripts",
                                args=['execute_scripts', script.name]))

        return actions

    def configure_action_argument_parser(self, action: str, argparser: argparse.ArgumentParser):
        super().configure_action_argument_parser(action, argparser)
        if action == 'execute_scripts':
            argparser.add_argument('scripts', nargs='+')
        elif action == 'add_user':
            argparser.add_argument('user', type=str)

    @action
    def enable_sql_apis(self, args):
        if args: pass
        for api in ['sqladmin.googleapis.com', 'sql-component.googleapis.com']:
            self.svc.enable_gcp_project_api(project_id=self.info.config['project_id'], api=api)

    @action
    def create_sql_instance(self, args) -> None:
        if args: pass
        cfg = self.info.config
        body = {
            "name": cfg['name'],
            "settings": {
                # https://cloud.google.com/sql/pricing#2nd-gen-instance-pricing
                "tier": cfg['machine-type'],
                "dataDiskSizeGb": str(cfg["data-disk-size-gb"] if "data-disk-size-gb" in cfg else 10),
                "dataDiskType": cfg["data-disk-type"] if "data-disk-type" in cfg else "PD_SSD",
                "databaseFlags": cfg['flags'] if 'flags' in cfg else [],
                "ipConfiguration": {
                    "requireSsl": cfg["require-ssl"] if "require-ssl" in cfg else False,
                    "authorizedNetworks": cfg["authorized-networks"] if "authorized-networks" in cfg else [],
                },
                "locationPreference": {
                    "zone": cfg['zone'],
                },
                "maintenanceWindow": cfg["maintenance"] if "maintenance" in cfg else {"day": 7, "hour": 3},
                "pricingPlan": "PER_USE",
                "userLabels": cfg['labels'] if 'labels' in cfg else {}
            },
            "databaseVersion": "MYSQL_5_7",
            "region": region_from_zone(cfg['zone']),
        }
        settings = body['settings']

        # apply backup information
        if "backup" in cfg:
            settings['backupConfiguration'] = {
                'enabled': cfg["backup"]['enabled'],
                'binaryLogEnabled': cfg["backup"]['enabled']
            }
            if cfg["backup"]['enabled'] and 'time' in cfg["backup"]:
                settings['backupConfiguration']['startTime'] = cfg["backup"]['time']

        # apply storage auto-resize
        if "storage-auto-resize" in cfg:
            settings['storageAutoResize'] = cfg["storage-auto-resize"]['enabled']
            if cfg["storage-auto-resize"]['enabled'] and 'limit' in cfg["storage-auto-resize"]:
                settings['storageAutoResizeLimit'] = str(cfg["storage-auto-resize"]['limit'])

        # create instance
        project_id: str = cfg['project_id']
        if self.info.verbose:  # pragma: no cover
            print(f"Creating Cloud SQL instance using:\n{json.dumps(body, indent=2)}")
        self.svc.create_gcp_sql_instance(project_id=project_id, body=body)

        # set 'root' password
        if self.info.verbose:  # pragma: no cover
            print(f"Updating root user's password")
        self.svc.update_gcp_sql_user(project_id=project_id, instance=cfg['name'], password=cfg['root-password'])

        # check for scripts that need to be executed
        if "scripts" in cfg:
            evaluator: ScriptEvaluator = ScriptEvaluator(svc=self.svc,
                                                         project_id=cfg['project_id'],
                                                         instance_name=cfg['name'],
                                                         root_password=cfg['root-password'],
                                                         zone=cfg['zone'],
                                                         scripts_data=self.info.config['scripts'],
                                                         context=cfg['scripts_ctx'] if 'scripts_ctx' in cfg else {})
            with evaluator as evaluator:
                evaluator.execute_scripts(scripts=evaluator.get_scripts_to_execute())

    @action
    def execute_scripts(self, args) -> None:
        cfg = self.info.config
        evaluator: ScriptEvaluator = ScriptEvaluator(svc=self.svc,
                                                     project_id=cfg['project_id'],
                                                     instance_name=cfg['name'],
                                                     root_password=cfg['root-password'],
                                                     zone=cfg['zone'],
                                                     scripts_data=self.info.config['scripts'],
                                                     context=cfg['scripts_ctx'] if 'scripts_ctx' in cfg else {})
        with evaluator as evaluator:
            scripts: Sequence[Script] = [evaluator.get_script(script_name) for script_name in args.scripts]
            evaluator.execute_scripts(scripts=scripts)

    @action
    def update_zone(self, args) -> None:
        if args: pass
        cfg = self.info.config
        self.svc.patch_gcp_sql_instance(project_id=cfg['project_id'], instance=cfg['name'], body={
            'settings': {
                'locationPreference': {
                    'zone': cfg['zone']
                }
            }
        })

    @action
    def update_machine_type(self, args) -> None:
        if args: pass
        cfg = self.info.config
        self.svc.patch_gcp_sql_instance(project_id=cfg['project_id'], instance=cfg['name'], body={
            'settings': {
                'tier': cfg["machine-type"]
            }
        })

    @action
    def update_backup(self, args) -> None:
        if args: pass
        cfg = self.info.config
        body = {
            'settings': {
                'backupConfiguration': {
                    'enabled': cfg['backup']['enabled'],
                    'binaryLogEnabled': cfg['backup']['enabled']
                }
            }
        }
        if cfg['backup']['enabled'] and 'time' in cfg['backup']:
            body['settings']['backupConfiguration']['startTime'] = cfg['backup']['time']

        self.svc.patch_gcp_sql_instance(project_id=cfg['project_id'], instance=cfg['name'], body=body)

    @action
    def update_data_disk_size(self, args) -> None:
        if args: pass
        cfg = self.info.config
        self.svc.patch_gcp_sql_instance(project_id=cfg['project_id'], instance=cfg['name'], body={
            'settings': {
                'dataDiskSizeGb': str(cfg["data-disk-size-gb"])
            }
        })

    @action
    def update_data_disk_type(self, args) -> None:
        if args: pass
        cfg = self.info.config
        self.svc.patch_gcp_sql_instance(project_id=cfg['project_id'], instance=cfg['name'], body={
            'settings': {
                'dataDiskType': cfg["data-disk-type"]
            }
        })

    @action
    def update_flags(self, args) -> None:
        if args: pass
        cfg = self.info.config
        self.svc.patch_gcp_sql_instance(project_id=cfg['project_id'], instance=cfg['name'], body={
            'settings': {
                'databaseFlags': cfg['flags']
            }
        })

    @action
    def update_require_ssl(self, args) -> None:
        if args: pass
        cfg = self.info.config
        self.svc.patch_gcp_sql_instance(project_id=cfg['project_id'], instance=cfg['name'], body={
            'settings': {
                'ipConfiguration': {
                    'requireSsl': cfg["require-ssl"]
                }
            }
        })

    @action
    def update_authorized_networks(self, args) -> None:
        if args: pass
        cfg = self.info.config
        self.svc.patch_gcp_sql_instance(project_id=cfg['project_id'], instance=cfg['name'], body={
            'settings': {
                'ipConfiguration': {
                    'authorizedNetworks': cfg["authorized-networks"]
                }
            }
        })

    @action
    def update_maintenance_window(self, args) -> None:
        if args: pass
        cfg = self.info.config
        self.svc.patch_gcp_sql_instance(project_id=cfg['project_id'], instance=cfg['name'], body={
            'settings': {
                'maintenanceWindow': cfg["maintenance"] if 'maintenance' in cfg else None
            }
        })

    @action
    def update_storage_auto_resize(self, args) -> None:
        if args: pass
        cfg = self.info.config
        body = {
            'settings': {
                'storageAutoResize': cfg["storage-auto-resize"]['enabled']
            }
        }
        if cfg["storage-auto-resize"]['enabled']:  # pragma: no cover
            body['settings']['storageAutoResizeLimit'] = cfg["storage-auto-resize"]['limit']
        self.svc.patch_gcp_sql_instance(project_id=cfg['project_id'], instance=cfg['name'], body=body)

    @action
    def update_labels(self, args) -> None:
        if args: pass
        cfg = self.info.config
        self.svc.patch_gcp_sql_instance(project_id=cfg['project_id'], instance=cfg['name'], body={
            'settings': {
                'userLabels': cfg['labels']
            }
        })

    @action
    def add_user(self, args) -> None:
        cfg = self.info.config
        for user in cfg['users']:
            if user['name'] == args.user:
                self.svc.create_gcp_sql_user(project_id=cfg['project_id'],
                                             instance_name=cfg['name'],
                                             user_name=user['name'],
                                             password=user['password'])
                return
        raise Exception(f"illegal state: could not find user '{args.user}' in users list: {pformat(cfg['users'])}")


def main():
    GcpCloudSql(json.loads(sys.stdin.read())).execute()  # pragma: no cover


if __name__ == "__main__":
    main()
