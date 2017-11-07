#!/usr/bin/env python

import argparse
import json
import subprocess
import sys

from colors import bold

from deployster.Context import Context
from deployster.Deployment import Deployment
from deployster.Util import ask, log


def parse_variable(expr):
    tokens = expr.split('=', 1)
    if len(tokens) != 2:
        raise argparse.ArgumentTypeError('bad variable declaration: %s' % expr)
    else:
        return {
            'key': tokens[0],
            'value': tokens[1]
        }


def main():
    argparser = argparse.ArgumentParser(description='Deployment automation.')
    argparser.add_argument('-y', '--yes', action='store_true', dest='assume_yes',
                           help="don't ask for confirmation before executing the deployment plan.")
    argparser.add_argument('-p', '--plan', action='store_true', dest='plan',
                           help="print deployment plan and exit.")
    argparser.add_argument('-v', '--verbose', action='store_true', dest='verbose',
                           help="print debugging information.")
    argparser.add_argument('--var', action='append', type=parse_variable, metavar='NAME=VALUE', dest='vars',
                           help='adds the given variable & value to the context.')
    argparser.add_argument('--var-file', action='append', metavar='FILE', dest='var_files',
                           help='adds the given variable files to the context.')
    argparser.add_argument('manifest', help='deployment manifest to execute.')
    args = argparser.parse_args()

    # test Docker is available
    process = subprocess.run(["docker", "run", "hello-world"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        print(f"Docker does not seem to be available. Here's the output from a test Docker run:\n", file=sys.stderr)
        print(process.stderr.decode('utf-8'), file=sys.stderr)
        exit(1)

    # build deployment context
    context = Context()
    for var in args.vars:
        context.add_variable(var['key'], var['value'])
    for var_file in args.var_files:
        context.add_file(var_file)
    if args.verbose:
        log(f"Context: {json.dumps(context.data, indent=2)}")

    # build deployment plan
    deployment = Deployment(context=context, manifest_file=args.manifest, verbose=args.verbose)

    # plan the deployment
    plan = deployment.plan()
    if args.plan:
        exit(0)

    # execute?
    if args.assume_yes or ask(bold('Execute?'), chars='yn', default='y') == 'y':
        deployment.execute(plan)


if __name__ == "__main__":
    main()
