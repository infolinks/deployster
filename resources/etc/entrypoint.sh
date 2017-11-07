#!/usr/bin/env bash

if [[ "THIS_WILL_NEVER_BE_TRUE" == "true" ]]; then
    PROJECT=${PROJECT}
    REGION=${REGION}
    NAME=${NAME}
fi

COMMAND=${1}
[[ -z "${COMMAND}" ]] && echo "usage: $0 <command> [command-args]" >&2 && exit 1

echo "Command: ${COMMAND}"
