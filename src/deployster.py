#!/usr/bin/env python3

import os
import termios
import traceback
from pathlib import Path

from colors import bold, underline, red, green

from args import parse_arguments
from context import Context
from manifest import Manifest
from plan import Plan
from util import ask, log, err, unindent, UserError


def get_version() -> str:
    if os.path.exists("/deployster/VERSION"):
        with open("/deployster/VERSION", 'r') as f:
            return f.read().strip()
    else:
        return "0.0.0"


def main():
    version = get_version()
    log(green(underline(bold(f"Deployster v{version}"))))
    log('')

    # create the shared context
    context: Context = Context(version)

    # parse arguments
    args = parse_arguments(context)
    log('')

    try:
        context.display()

        # load manifest
        manifest: Manifest = Manifest(context=context, manifest_files=args.manifests)
        manifest.display_plugs()

        # build the deployment plan, display, and potentially execute it
        plan: Plan = Plan(work_dir=Path(f"/deployster/work/deployment"), manifest=manifest)
        plan.bootstrap(args.pull)
        plan.resolve()
        plan.display()
        if args.plan or plan.empty:
            exit(0)

        execute_plan: bool = args.assume_yes or ask(bold('Execute?'), chars='yn', default='n') == 'y'
        log('')

        if execute_plan:
            plan.execute()

    except UserError as e:
        if args.verbose:
            err(red(traceback.format_exc()))
        else:
            err(red(e.message))
        exit(1)

    except termios.error as e:
        unindent(fully=True)
        err('')
        err(red(f"IO error: {e}"))
        exit(1)

    except KeyboardInterrupt:
        unindent(fully=True)
        err('')
        err(red(f"Interrupted."))
        exit(1)

    except Exception:
        # always print stacktrace since this exception is an unexpected exception
        err(red(traceback.format_exc()))
        exit(1)


if __name__ == "__main__":
    main()
