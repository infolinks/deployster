#!/usr/bin/env bash

set -ex

PROJECT="${1}"
./.buildkite/build.sh local > /dev/null && echo ''
./bin/deployster.sh --var gcp_project=${PROJECT} --var-file ./examples/context.default.yaml ./examples/example1.yaml
