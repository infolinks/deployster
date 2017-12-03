#!/usr/bin/env bash

# default deployster version to "latest" unless supplied as environment variable already
[[ "${DEPLOYSTER_VERSION}" == "" ]] && DEPLOYSTER_VERSION="${DVERSION}"
[[ "${DEPLOYSTER_VERSION}" == "" ]] && DEPLOYSTER_VERSION="latest"

# set Docker flags
[[ -t 1 ]] && DOCKER_FLAGS="${DOCKER_FLAGS} -it"

# run!
mkdir -vp ~/.deployster
docker run ${DOCKER_FLAGS} \
           -v $(cd ~/.deployster; pwd):/root/.deployster \
           -v $(pwd):/deployster/workspace \
           -v $(pwd)/work:/deployster/work \
           -v /var/run/docker.sock:/var/run/docker.sock \
           infolinks/deployster:${DEPLOYSTER_VERSION} \
           --var _dir=$(pwd) \
           $@
