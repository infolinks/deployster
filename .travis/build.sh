#!/usr/bin/env bash

set -e

docker build -t infolinks/deployster:${TRAVIS_COMMIT} .

if [[ ${TRAVIS_TAG} =~ ^v[0-9]+$ ]]; then
    docker tag infolinks/deployster:${TRAVIS_COMMIT} infolinks/deployster:${TRAVIS_TAG}
    docker push infolinks/deployster:${TRAVIS_TAG}
    docker tag infolinks/deployster:${TRAVIS_COMMIT} infolinks/deployster:latest
    docker push infolinks/deployster:latest
fi
