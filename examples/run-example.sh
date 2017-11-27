#!/usr/bin/env bash

VERSION="0.0.0"

echo "Building..." >&2
OUTPUT=$($(dirname $0)/../.buildkite/build.sh ${VERSION} 2>&1)
[[ $? != 0 ]] && echo "Build failed:" >&2 && echo "${OUTPUT}" >&2 && exit 1

DEPLOYSTER_VERSION=${VERSION} source $(dirname $0)/../deployster.sh --no-pull $@
