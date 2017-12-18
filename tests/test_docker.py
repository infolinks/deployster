import json
from pathlib import Path

import pytest

from mock_external_services import MockDockerInvoker
from util import UserError, Logger


def test_docker_invoker_run_json():
    with pytest.raises(UserError, match='Docker command terminated with exit code #-1'):
        MockDockerInvoker(return_code=-1,
                          stderr='ERROR!',
                          stdout='invalid JSON here').run_json(logger=Logger(),
                                                               local_work_dir=Path('/'),
                                                               container_work_dir='/',
                                                               image='some_image',
                                                               entrypoint=None,
                                                               args=None,
                                                               input=None)

    with pytest.raises(UserError, match='Docker command terminated with exit code #-1'):
        MockDockerInvoker(return_code=-1,
                          stderr='ERROR!',
                          stdout='invalid JSON here').run(logger=Logger(),
                                                          local_work_dir=Path('/'),
                                                          container_work_dir='/',
                                                          image='some_image',
                                                          entrypoint=None,
                                                          args=None,
                                                          input=None)

    with pytest.raises(UserError, match='Docker command did not provide any JSON back'):
        MockDockerInvoker(return_code=0,
                          stderr='ERROR!',
                          stdout='').run_json(logger=Logger(),
                                              local_work_dir=Path('/'),
                                              container_work_dir='/',
                                              image='some_image',
                                              entrypoint=None,
                                              args=None,
                                              input=None)

    with pytest.raises(UserError, match='Docker command provided invalid JSON'):
        MockDockerInvoker(return_code=0,
                          stderr='ERROR!',
                          stdout='{invalidate JSON here too').run_json(logger=Logger(),
                                                                       local_work_dir=Path('/'),
                                                                       container_work_dir='/',
                                                                       image='some_image',
                                                                       entrypoint=None,
                                                                       args=None,
                                                                       input=None)

    data: dict = {'k1': 'v1'}
    result: dict = MockDockerInvoker(return_code=0,
                                     stderr='ERROR!',
                                     stdout=json.dumps(data)).run_json(logger=Logger(),
                                                                       local_work_dir=Path('/'),
                                                                       container_work_dir='/',
                                                                       image='some_image',
                                                                       entrypoint=None,
                                                                       args=None,
                                                                       input=None)
    assert data == result

    MockDockerInvoker(return_code=0, stderr='ERROR!', stdout=json.dumps(data)).run(logger=Logger(),
                                                                                   local_work_dir=Path('/'),
                                                                                   container_work_dir='/',
                                                                                   image='some_image',
                                                                                   entrypoint=None,
                                                                                   args=None,
                                                                                   input=None)
