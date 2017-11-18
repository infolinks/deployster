#!/usr/bin/env bash

VERSION="${1}"
[[ -z "${VERSION}" ]] && echo "usage: $0 <version>" >&2 && exit 1

set -ex

echo "Building & pushing versioned images..."
$(dirname $0)/build.sh "${VERSION}" push

# tag images as VERSION and 'latest', then push them to Docker Hub
gcloud docker --authorize-only
for docker_file in $(find "./resources" -name "Dockerfile"); do
    IMAGE_DIR="${docker_file//\/Dockerfile/}"
    IMAGE_PATH="${IMAGE_DIR//\.\/resources\//}"
    IMAGE_NAME="infolinks/deployster-${IMAGE_PATH//\//-}"

    docker tag "${IMAGE_NAME}:${VERSION}" "${IMAGE_NAME}:latest"
    docker push "${IMAGE_NAME}:latest"
done

docker tag "infolinks/deployster:${VERSION}" "infolinks/deployster:latest"
docker push "infolinks/deployster:latest"
