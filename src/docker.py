import datetime
import json
import os
from io import TextIOWrapper
from pathlib import Path
from subprocess import Popen, PIPE
from threading import Thread
from time import sleep
from typing import Sequence, MutableSequence, Tuple

from util import UserError, Logger


class DockerInvoker:

    def __init__(self, volumes: Sequence[str] = None) -> None:
        super().__init__()
        self._volumes: Sequence[str] = volumes

    def _invoke(self,
                local_work_dir: Path,
                container_work_dir: str,
                image: str,
                entrypoint: str = None,
                args: Sequence[str] = None,
                input: dict = None,
                stderr_logger: Logger = None,
                stdout_logger: Logger = None) -> Tuple[int, str, str]:

        # the timestamp serves as a unique invocation ID in the work dir
        timestamp = datetime.datetime.utcnow().isoformat("T") + "Z"
        os.makedirs(str(local_work_dir), exist_ok=True)
        stderr_file = local_work_dir / f"stderr-{timestamp}.json"
        stdout_file = local_work_dir / f"stdout-{timestamp}.json"

        # save the input we will send to the process in the work_dir (for reference)
        if input is not None:
            with open(local_work_dir / f"stdin-{timestamp}.json", 'w') as f:
                f.write(json.dumps(input if input else {}, indent=2))

        # build the full "docker run ..." command (volumes, entrypoint, image & args)
        cmd: MutableSequence[str] = ["docker", "run", "-i", f"--workdir={container_work_dir}"]
        for volume in self._volumes if self._volumes is not None else []:
            cmd.extend(["--volume", volume])
        if entrypoint is not None: cmd.extend(["--entrypoint", entrypoint])
        cmd.append(image)
        if args:
            cmd.extend(args)

        # start the process
        process = Popen(cmd, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE, universal_newlines=True)

        # thread handler for writing stderr to file, and optionally to a given logger
        def stderr_handler(stream: TextIOWrapper):
            with open(stderr_file, 'w') as f:
                for line in iter(stream.readline, ''):
                    line = line[0:len(line) - 1]
                    f.write(line + '\n')
                    if stderr_logger:
                        stderr_logger.info(line)

        # thread handler for writing stdout to file, and optionally to a given logger
        def stdout_handler(stream: TextIOWrapper):
            with open(stdout_file, 'w') as f:
                for line in iter(stream.readline, ''):
                    line = line[0:len(line) - 1]
                    f.write(line + '\n')
                    if stdout_logger:
                        stdout_logger.info(line)

        # setup output threads
        stderr_thread = Thread(target=stderr_handler,
                               name=f"{image}-{timestamp}-stderr",
                               kwargs={'stream': process.stderr},
                               daemon=True) if stderr_handler else None
        stderr_thread.start()
        stdout_thread = Thread(target=stdout_handler,
                               name=f"{image}-{timestamp}-stdout",
                               kwargs={'stream': process.stdout},
                               daemon=True) if stdout_handler else None
        stdout_thread.start()

        # send input to process (if input was provided to us)
        if input is not None:
            process.stdin.write(json.dumps(input, indent=2))
            process.stdin.close()

        # while process is alive, pipe stderr to console, and stdout into memory
        while process.poll() is None:
            sleep(1)

        # ensure threads are done
        stderr_thread.join()
        stdout_thread.join()

        # validate exit-code is zero, and if so, parse stdout into JSON, save it to file, and return JSON as dict
        return process.returncode, open(stdout_file, 'r').read(), open(stderr_file, 'r').read()

    def run(self,
            logger: Logger,
            local_work_dir: Path,
            container_work_dir: str,
            image: str,
            entrypoint: str = None,
            args: Sequence[str] = None,
            input: dict = None) -> None:

        return_code, stdout, stderr = self._invoke(local_work_dir=local_work_dir,
                                                   container_work_dir=container_work_dir,
                                                   image=image,
                                                   entrypoint=entrypoint,
                                                   args=args,
                                                   input=input,
                                                   stderr_logger=logger,
                                                   stdout_logger=logger)

        if return_code != 0:
            raise UserError(f"Docker command terminated with exit code #{return_code}!")

    def run_json(self,
                 logger: Logger,
                 local_work_dir: Path,
                 container_work_dir: str,
                 image: str,
                 entrypoint: str = None,
                 args: Sequence[str] = None,
                 input: dict = None):

        return_code, stdout, stderr = self._invoke(local_work_dir=local_work_dir,
                                                   container_work_dir=container_work_dir,
                                                   image=image,
                                                   entrypoint=entrypoint,
                                                   args=args,
                                                   input=input,
                                                   stderr_logger=logger)

        if return_code != 0:
            raise UserError(f"Docker command terminated with exit code #{return_code}!")
        elif stdout:
            try:
                return json.loads(stdout)
            except json.decoder.JSONDecodeError as e:
                raise UserError(f"Docker command provided invalid JSON: {e.msg}") from e
        else:
            raise UserError(f"Docker command did not provide any JSON back!")
