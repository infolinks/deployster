#!/usr/bin/env bash

VERSION="0.0.0"

echo "Building..." >&2
$(dirname $0)/../.buildkite/build.sh ${VERSION} 2>&1 1>> ./.build.log
[[ $? != 0 ]] && echo "Build failed! (inspect '.build.log' for details)" >&2 && exit 1

source $(dirname $0)/../deployster.sh --no-pull $@
