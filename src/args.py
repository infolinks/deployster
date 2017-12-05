import argparse
import os

from context import Context
from util import warn, yellow


def parse_arguments(context: Context):
    class VariableAction(argparse.Action):

        def __init__(self, option_strings, dest, nargs=None, const=None, default=None, type=None, choices=None,
                     required=False, help=None, metavar=None):
            if const is not None:
                raise ValueError("'const' not allowed with VariableAction")
            if type is not None and type != str:
                raise ValueError("'type' must be 'str' (or None)")
            super().__init__(option_strings, dest, nargs, const, default, type, choices, required, help, metavar)

        def __call__(self, parser, namespace, values, option_string=None):
            tokens = values.split('=', 1)
            if len(tokens) != 2:
                raise argparse.ArgumentTypeError(f"bad variable: '{values}'")
            else:
                var_name = tokens[0]
                var_value = tokens[1]
                if var_value[0] == '"' and var_value[-1] == '"':
                    var_value = var_value[1:-1]
                context.add_variable(var_name, var_value)

    class VariablesFileAction(argparse.Action):

        def __init__(self, option_strings, dest, nargs=None, const=None, default=None, type=None, choices=None,
                     required=False, help=None, metavar=None):
            if const is not None:
                raise ValueError("'const' not allowed with VariableAction")
            if type is not None and type != str:
                raise ValueError("'type' must be 'str' (or None)")
            super().__init__(option_strings, dest, nargs, const, default, type, choices, required, help, metavar)

        def __call__(self, parser, namespace, values, option_string=None):
            if os.path.exists(values):
                context.add_file(values)
            else:
                warn(yellow(
                    f"WARNING: context file '{values}' does not exist (manifest processing might result in errors)."))

    # parse arguments
    argparser = argparse.ArgumentParser(description=f"Deployment automation tool, v{context.version}.",
                                        epilog="Written by Infolinks Inc. (https://github.com/infolinks/deployster)")
    argparser.add_argument('--no-pull', dest='pull', action='store_false',
                           help='skip resource Docker images pulling (rely on Docker default)')
    argparser.add_argument('--var', action=VariableAction, metavar='NAME=VALUE', dest='context',
                           help='makes the given variable available to the deployment manifest')
    argparser.add_argument('--var-file', action=VariablesFileAction, metavar='FILE', dest='context',
                           help='makes the variables in the given file available to the deployment manifest')
    argparser.add_argument('manifests', nargs='+', help='the deployment manifest to execute.')
    argparser.add_argument('-p', '--plan', action='store_true', dest='plan', help="print deployment plan and exit")
    argparser.add_argument('-y', '--yes', action='store_true', dest='assume_yes',
                           help="don't ask for confirmation before executing the deployment plan.")
    argparser.add_argument('-v', '--verbose', action='store_true', dest='verbose', help="print debugging information.")
    return argparser.parse_args()
