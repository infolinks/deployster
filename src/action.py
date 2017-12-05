import datetime
import json
import os
from json import JSONDecodeError
from pathlib import Path
from typing import Sequence

from util import UserError


class Action:

    @staticmethod
    def from_json(data: dict,
                  default_name: str = None, default_description: str = None,
                  default_image: str = None, default_entrypoint: str = None, default_args: Sequence[str] = None):
        name: str = data['name'] if 'name' in data else default_name
        description: str = data['description'] if 'description' in data else default_description
        image: str = data['image'] if 'image' in data else default_image
        entrypoint: str = data['entrypoint'] if 'entrypoint' in data else default_entrypoint
        args: str = data['args'] if 'args' in data else default_args
        return Action(name=name, description=description, image=image, entrypoint=entrypoint, args=args)

    def __init__(self,
                 name: str,
                 description: str,
                 image: str,
                 entrypoint: str = None,
                 args: Sequence[str] = None) -> None:
        super().__init__()
        self._name: str = name
        self._description: str = description
        self._image: str = image
        self._entrypoint: str = entrypoint
        self._args: Sequence[str] = args if args else []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def image(self) -> str:
        return self._image

    @property
    def entrypoint(self) -> str:
        return self._entrypoint

    @property
    def args(self) -> Sequence[str]:
        return self._args

    def execute(self,
                workspace_dir: Path,
                work_dir: Path,
                volumes: Sequence[str] = None,
                stdin: dict = None,
                expect_json=True):
        os.makedirs(str(work_dir), exist_ok=True)

        command = ["docker", "run", "-i"]
        command.extend(["--volume", f"{workspace_dir}:/deployster/workspace"])

        # setup volumes
        if volumes:
            for volume in volumes:
                command.extend(["--volume", volume])

        # setup entrypoint
        if self.entrypoint:
            command.extend(["--entrypoint", self.entrypoint])

        # setup args
        command.append(self.image)
        if self.args:
            command.extend(self.args)

        # generate timestamp
        timestamp = datetime.datetime.utcnow().isoformat("T") + "Z"

        # save stdin state file
        with open(work_dir / f"stdin-{timestamp}.json", 'w') as f:
            f.write(json.dumps(stdin if stdin else {}, indent=2))

        # execute
        process = os.subprocess.run(command,
                                    input=json.dumps(stdin, indent=2) if stdin else '{}',
                                    encoding='utf-8',
                                    stdout=os.subprocess.PIPE, stderr=os.subprocess.PIPE)

        # save stdout & stderr state files
        with open(work_dir / f"stdout-{timestamp}.json", 'w') as f:
            if expect_json:
                if process.stdout:
                    try:
                        f.write(json.dumps(json.loads(process.stdout), indent=2))
                    except:
                        f.write(process.stdout)
                else:
                    f.write('')
            else:
                if process.stdout:
                    f.write(process.stdout)
                else:
                    f.write('')
        with open(work_dir / f"stderr-{timestamp}.json", 'w') as f:
            if process.stderr:
                f.write(process.stderr)
            else:
                f.write('')

        # validate exit-code, fail if non-zero
        if process.returncode != 0:
            raise UserError(f"action '{self.name}' failed with exit code #{process.returncode}:\n{process.stderr}")

        # process provided output
        elif process.stdout:
            if expect_json:
                try:
                    return json.loads(process.stdout)
                except JSONDecodeError as e:
                    raise UserError(f"action '{self.name}' provided invalid JSON:\n{process.stdout}") from e
            else:
                return process.stdout

        # otherwise, if JSON expected, fail (empty response & JSON expected)
        elif expect_json:
            raise UserError(f"protocol error: action '{self.name}' expected to provide JSON, but was empty.")

        # otherwise, no response
        else:
            return None
