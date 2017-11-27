import argparse
import subprocess
from typing import Any, Callable

from dresources import DResource


# noinspection PyAbstractClass
class GcpResource(DResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.add_plug(name='gcp-service-account',
                      container_path='/deployster/service-account.json',
                      optional=False, writable=False)

    # TODO: remove this code
    # def execute_action(self, action_name: str, action_method: Callable[..., Any], args: argparse.Namespace):
    #     if action_name != 'init':
    #         sa_file_path: str = self.get_plug("gcp-service-account").container_path
    #         subprocess.run(f"gcloud auth activate-service-account --key-file {sa_file_path}", check=True, shell=True)
    #     super().execute_action(action_name, action_method, args)
