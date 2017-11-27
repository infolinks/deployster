#!/usr/bin/env bash

# default deployster version to "latest" unless supplied as environment variable already
[[ "${DEPLOYSTER_VERSION}" == "" ]] && DEPLOYSTER_VERSION="latest"

# run!
mkdir -vp ~/.deployster
docker run $([[ -t 1 ]] && echo -n "-it" || echo -n "") \
           -v $(cd ~/.deployster; pwd):/root/.deployster \
           -v $(pwd):/deployster/workspace \
           -v $(pwd)/work:/deployster/work \
           -v /var/run/docker.sock:/var/run/docker.sock \
           infolinks/deployster:${DEPLOYSTER_VERSION} \
           $@
