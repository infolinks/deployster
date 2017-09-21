import json
import sys

import os
from jsonmerge import Merger


def load_environment(name, env_files):
    env_merger = Merger({})
    env = {'name': name}
    at_least_one_env_file_found = False
    for env_file in env_files:
        if os.path.isfile(env_file):
            sys.stderr.write("Merging '%s' into environment context\n" % env_file)
            env = env_merger.merge(env, json.loads(open(env_file, mode='r').read()))
            at_least_one_env_file_found = True
        else:
            sys.stderr.write("WARNING: environment file '%s' does not exist.\n" % env_file)

    if not at_least_one_env_file_found:
        raise IOError("No environment files exist! List is: %s" % json.dumps(env_files))

    sys.stderr.write("Writing full environment to '.merged-environment.json'\n")
    merged_env_file = open('./.merged-environment.json', 'w')
    try:
        merged_env_file.write(json.dumps(env, indent=2))
    finally:
        merged_env_file.close()

    return env
