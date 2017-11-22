#!/usr/bin/env bash

# Simple IntelliJ IDEA hack to prevent false warnings on undefined environment variables
if [[ "THIS_WILL_NEVER" == "BE_TRUE" ]]; then
    DEPLOYSTER_VERSION=${DEPLOYSTER_VERSION}
fi

# default deployster version to "latest" unless supplied as environment variable already
[[ "${DEPLOYSTER_VERSION}" == "" ]] && DEPLOYSTER_VERSION="latest"

# run!
docker run -it \
           -v $(pwd):/deployster/workspace \
           -v $(pwd)/work:/deployster/work \
           -v /var/run/docker.sock:/var/run/docker.sock \
           infolinks/deployster:${DEPLOYSTER_VERSION} \
           $@