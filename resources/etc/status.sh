#!/usr/bin/env bash

if [[ "THIS_WILL_NEVER_BE_TRUE" == "true" ]]; then
    PROJECT=${PROJECT}
    REGION=${REGION}
    NAME=${NAME}
fi

eval "$(jq -r '@sh "PROJECT=\(.project) REGION=\(.region) NAME\(.name)"')"
[[ -z "${PROJECT}" || -z "${REGION}" || -z "${NAME}" ]] && echo "missing 'project', 'region' or 'name arguments" >&2 && exit 1

