#!/usr/bin/env python3

import argparse
import os
import termios
import traceback

from colors import bold, underline, green

from context import Context, ConfirmationMode
# from plan import Plan
from executor import Executor
from manifest import Manifest
from util import UserError, Logger


def parse_arguments(context: Context):
    with Logger(indent_amount=0, spacious=False) as logger:

        class VariableAction(argparse.Action):

            def __init__(self, option_strings, dest, nargs=None, const=None, default=None, type=None, choices=None,
                         required=False, help=None, metavar=None):
                if const is not None:
                    raise ValueError("internal error: 'const' not allowed with VariableAction")
                if type is not None and type != str:
                    raise ValueError("internal error: 'type' must be 'str' (or None)")
                super().__init__(option_strings, dest, nargs, const, default, type, choices, required, help, metavar)

            def __call__(self, parser, namespace, values, option_string=None):
                tokens = values.split('=', 1)
                if len(tokens) != 2:
                    raise argparse.ArgumentTypeError(f"bad variable declaration: '{values}'")
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
                    raise ValueError("internal error: 'const' not allowed with VariableAction")
                if type is not None and type != str:
                    raise ValueError("internal error: 'type' must be 'str' (or None)")
                super().__init__(option_strings, dest, nargs, const, default, type, choices, required, help, metavar)

            def __call__(self, parser, namespace, values, option_string=None):
                if os.path.exists(values):
                    context.add_file(values)
                else:
                    logger.warn(f"Variables file '{values}' is missing!")

        # parse arguments
        argparser = argparse.ArgumentParser(description=f"Deployment automation tool, v{context.version}.",
                                            epilog="Written by Infolinks @ https://github.com/infolinks/deployster")
        argparser.add_argument('-c', '--confirm', dest='confirm', default=ConfirmationMode.ACTION.name,
                               choices=[mode.name for mode in list(ConfirmationMode)], help='confirmation mode')
        argparser.add_argument('--var', action=VariableAction, metavar='NAME=VALUE', dest='context',
                               help='makes the given variable available to the deployment manifest')
        argparser.add_argument('--var-file', action=VariablesFileAction, metavar='FILE', dest='context',
                               help='makes the variables in the given file available to the deployment manifest')
        argparser.add_argument('manifests', nargs='+', help='the deployment manifest to execute.')
        argparser.add_argument('-p', '--plan', action='store_true', dest='plan', help="print deployment plan and exit")
        argparser.add_argument('-v', '--verbose', action='store_true', dest='verbose', help="increase verbosity")
        return argparser.parse_args()


def main():
    # create the shared context
    context: Context = Context()
    print('')
    with Logger(green(underline(bold(f":heavy_check_mark: Deployster v{context.version}")))) as logger:
        logger.info(f":smile: {bold('Deploy with pleasure!')}")

    try:
        # load the auto files from user home and cwd
        context.load_auto_files()

        # create the shared context and parse the command-line arguments
        args = parse_arguments(context)
        context.verbose = args.verbose
        context.confirm = ConfirmationMode[args.confirm]

        # display the context
        context.display()

        # load & display the manifest
        manifest: Manifest = Manifest(context=context, manifest_files=args.manifests)
        manifest.display_plugs()

        # build the deployment plan, display, and potentially execute it
        executor: Executor = Executor(manifest=manifest)
        executor.bootstrap()
        executor.execute()

    except UserError as e:
        with Logger(indent_amount=0, spacious=False) as logger:
            if context and context.verbose:
                logger.error(traceback.format_exc().strip())
            else:
                logger.error(e.message)
        exit(1)

    except termios.error as e:
        with Logger(indent_amount=0, spacious=False) as logger:
            logger.error(f"IO error: {e}")
        exit(1)

    except KeyboardInterrupt:
        with Logger(indent_amount=0, spacious=False) as logger:
            logger.error(f"Interrupted.")
        exit(1)

    except Exception:
        # always print stacktrace since this exception is an unexpected exception
        with Logger(indent_amount=0, spacious=False) as logger:
            logger.error(traceback.format_exc().strip())
        exit(1)


if __name__ == "__main__":
    main()
