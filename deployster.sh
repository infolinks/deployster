#!/usr/bin/env bash

# simple IntelliJ IDEA hack to prevent undefined-env-vars warnings
if [[ "THIS_WILL" == "NEVER_BE_TRUE" ]]; then
    VERSION=${VERSION}
fi

# default deployster version to "latest" unless supplied as environment variable already
[[ "${VERSION}" == "" ]] && VERSION="latest"

# setup paths to mount
CONF_DIR="$(mkdir -p ~/.deployster; cd ~/.deployster; pwd)"
WORKSPACE_DIR="$(pwd)"
WORK_DIR="$(mkdir -p ./work; cd ./work; pwd)"

# set Docker flags
[[ -t 1 ]] && TTY_FLAGS="${TTY_FLAGS} -it"

# run!
docker run ${TTY_FLAGS} \
           -v ${CONF_DIR}:${CONF_DIR}:ro \
           -v ${WORKSPACE_DIR}:${WORKSPACE_DIR}:ro \
           -v ${WORK_DIR}:${WORK_DIR}:rw \
           -v /var/run/docker.sock:/var/run/docker.sock \
           -e CONF_DIR="${CONF_DIR}" \
           -e WORKSPACE_DIR="${WORKSPACE_DIR}" \
           -e WORK_DIR="${WORK_DIR}" \
           --workdir="${WORKSPACE_DIR}" \
           infolinks/deployster:${VERSION} \
           $@
