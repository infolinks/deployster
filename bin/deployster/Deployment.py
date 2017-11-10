import os
import shutil
from os.path import basename
from pathlib import Path

import jinja2
import yaml
from colors import *
from jinja2.exceptions import UndefinedError

from deployster.Plug import Plug
from deployster.Util import log, err, indent, unindent
from deployster.resource.Resource import Resource
from deployster.resource.ResourceStatus import ResourceStatus


class UndefinedManifestVariableError(UndefinedError):
    def __init__(self, manifest_file, message=None):
        super().__init__(f"undefined variable referenced in '{manifest_file}' ({message})")


class UnknownResourceError(UndefinedError):
    def __init__(self, resource_name, manifest_file):
        super().__init__(f"unknown resource: {resource_name} referenced in '{manifest_file}'")


class ResourceDependencyResolver:

    def __init__(self, deployment, resources):
        self._deployment = deployment
        self._resources = []
        self._scan(resources)

    def _scan(self, resources):
        # TODO: detect circular dependencies
        for resource in resources:
            if resource not in self._resources:
                self._scan([self._deployment.resource(dep_name) for dep_name in resource.dependencies])
                self._resources.append(resource)

    @property
    def resources(self):
        return self._resources

    def process(self, action):
        results = []
        for resource in self._resources:
            results.append(action(resource))
        return results


class Deployment:

    def __init__(self, context, manifest_file, verbose=False):
        self._name = basename(manifest_file)
        self._plugs = {}
        self._resources = {}
        self._verbose = verbose
        self._manifest_file = manifest_file

        # setup work directory
        self._work_dir = Path(f'./work/deployment/{self.name}').resolve()
        try:
            shutil.rmtree(self._work_dir)
        except FileNotFoundError:
            pass
        os.makedirs(self._work_dir)

        # read manifest
        manifest_text = open(manifest_file, 'r').read()
        environment = jinja2.Environment(undefined=jinja2.StrictUndefined)
        manifest_template = environment.from_string(manifest_text)
        try:
            self._manifest = yaml.load(manifest_template.render(context.data))
        except UndefinedError as e:
            err(red(f"manifest error: {e.message}"))
            exit(1)

        # parse plugs
        if 'plugs' in self._manifest:
            for plug_name, plug in self._manifest['plugs'].items():
                self._plugs[plug_name] = Plug(plug_name, plug)

        # parse resources
        log(bold(underline("\n:mag_right: Initializing...\n")))
        indent()
        if 'resources' in self._manifest:
            resources = self._manifest['resources']
            if isinstance(resources, dict):
                for resource_name, resource in resources.items():
                    self._resources[resource_name] = Resource(self, resource_name, resource)
            else:
                err(red("invalid manifest: 'resources' must be a map"))
                exit(1)
        unindent()

    @property
    def verbose(self):
        return self._verbose

    @property
    def name(self):
        return self._name

    @property
    def plugs(self):
        return self._plugs

    def resource(self, name):
        if name in self.resources:
            return self.resources[name]
        else:
            raise UnknownResourceError(resource_name=name, manifest_file=self._manifest_file)

    @property
    def resources(self):
        return self._resources

    @property
    def resource_types(self):
        return {resource.type for resource in self.resources}

    @property
    def work_dir(self):
        return self._work_dir

    def plan(self):
        processor = ResourceDependencyResolver(self, self.resources.values())

        # Refresh resources state
        ##################################
        log(bold(underline("\n:hourglass: Refreshing state...\n")))
        indent()
        for resource in processor.resources:
            resource.refresh_state()
        unindent()

        # Printout the deployment plan
        ##################################
        log(bold(underline("\n:clipboard: Deployment plan:\n")))

        def resource_status(symbol, resource):
            return f":{symbol}: " + underline(f"{resource.name} {italic('(' + resource.type + ')')}\n")

        def resource_action(action):
            return f":wrench: {action.description}"

        actions = []
        invalid = False

        indent()
        for res in processor.resources:
            if res.state.status == ResourceStatus.VALID:
                log(green(resource_status("white_check_mark", res)))

            elif res.state.status == ResourceStatus.STALE:
                log(yellow(resource_status("point_right", res)))
                indent()
                for action in res.state.actions:
                    log(resource_action(action))
                    actions.append(action)
                unindent()

            elif res.state.status == ResourceStatus.MISSING:
                log(yellow(resource_status("heavy_plus_sign", res)))
                indent()
                for action in res.state.actions:
                    log(resource_action(action))
                    actions.append(action)
                unindent()

            elif res.state.status == ResourceStatus.INVALID:
                log(red(resource_status("x", res)))
                indent()
                log(red(res.state.reason))
                unindent()
                invalid = True

            log('')

        unindent()

        log('')
        if invalid:
            log(bold(red(f"Invalid resources found, plan cannot be executed.\n")))
            exit(1)

        return actions

    # noinspection PyMethodMayBeStatic
    def execute(self, plan):
        log(bold("\n:dizzy: " + underline("Executing plan...\n")))
        indent()
        for action in plan:
            indent()
            action.execute()
            unindent()
        unindent()
        log('')
