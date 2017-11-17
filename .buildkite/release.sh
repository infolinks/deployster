#!/usr/bin/env bash

TAG="${1}"
[[ -z "${TAG}" ]] && echo "usage: $0 <tag> <version>" >&2 && exit 1

VERSION="${2}"
[[ -z "${VERSION}" ]] && echo "usage: $0 <tag> <version>" >&2 && exit 1

set -ex

# tag images as VERSION and 'latest', then push them to Docker Hub
gcloud docker --authorize-only
for docker_file in $(find "./resources" -name "Dockerfile"); do
    IMAGE_DIR="${docker_file//\/Dockerfile/}"
    IMAGE_PATH="${IMAGE_DIR//\.\/resources\//}"
    IMAGE_NAME="infolinks/deployster/${IMAGE_PATH}"

    docker tag "${IMAGE_NAME}:${TAG}" "${IMAGE_NAME}:${VERSION}"
    docker push "${IMAGE_NAME}:${VERSION}"
    docker tag "${IMAGE_NAME}:${TAG}" "${IMAGE_NAME}:latest"
    docker push "${IMAGE_NAME}:latest"
done

docker tag "infolinks/deployster:${TAG}" "infolinks/deployster:${VERSION}"
docker push "infolinks/deployster:${VERSION}"
docker tag "infolinks/deployster:${TAG}" "infolinks/deployster:latest"
docker push "infolinks/deployster:latest"
