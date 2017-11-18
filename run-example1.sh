#!/usr/bin/env bash

PROJECT="${1}"
# TODO: generalize this script

set -ex

./.buildkite/build.sh local > /dev/null && echo ''

./bin/deployster.sh --var gcp_project=infolinks-test \
                    --var-file ./examples/context.default.yaml \
                    ./examples/example1.yaml
