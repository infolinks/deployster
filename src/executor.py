import os
import shutil
import subprocess
from subprocess import PIPE

from colors import underline, faint, bold

from context import ConfirmationMode
from manifest import Manifest
from util import UserError, Logger, italic, ask


class Executor:

    def __init__(self, manifest: Manifest) -> None:
        super().__init__()
        self._manifest: Manifest = manifest

    def bootstrap(self) -> None:
        with Logger(f":hourglass: {underline('Bootstrapping:')}") as logger:

            # verify Docker is available
            logger.info(f":wrench: Verifying that Docker is available...")
            process = subprocess.run(["docker", "run", "hello-world"], stdout=PIPE, stderr=PIPE)
            if process.returncode != 0:
                raise UserError(f"Docker is not available. Here's output from a test run:\n"
                                f"=======================================================\n"
                                f"{process.stderr.decode('utf-8')}")

            # clean work dir
            logger.info(f":wrench: Cleaning work directory (at {italic(faint(self._manifest.context.work_dir))})")
            try:
                for file in os.listdir(str(self._manifest.context.work_dir)):
                    shutil.rmtree(str(self._manifest.context.work_dir / file))
            except FileNotFoundError:
                pass

            # initialize resources
            for resource in self._manifest.resources.values():
                resource.initialize()

    def execute(self) -> None:
        with Logger(f":dizzy: {underline('Execution:')}") as logger:
            if self._manifest.context.confirm == ConfirmationMode.ONCE:
                if ask(logger=logger, message=bold('Execute?'), chars='yn', default='n') == 'n':
                    raise UserError(f"user aborted")
            for resource in self._manifest.resources.values():
                resource.execute()
