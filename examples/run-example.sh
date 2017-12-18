#!/usr/bin/env bash

VERSION="0.0.0"
time $(dirname $0)/../.buildkite/build.sh ${VERSION}
[[ $? != 0 ]] && echo "Build failed!" >&2 && exit 1

DEPLOYSTER_VERSION="${VERSION}" \
    source $(dirname $0)/../deployster.sh --var bar="hi!" \
                                          --var-file vars.1.yaml \
                                          --var-file vars.2.yaml \
                                          $@
