#!/usr/bin/env bash

TAG="${1}"
[[ -z "${TAG}" ]] && echo "usage: $0 <version>" >&2 && exit 1

echo "Building & pushing versioned images..." >&2
$(dirname $0)/build.sh "${TAG}" push

# setup
DEPLOYSTER_HOME=$(cd $(dirname $0)/..; pwd)
RESOURCES_HOME="${DEPLOYSTER_HOME}/resources"
TAG_PREFIX="infolinks/deployster"

echo "Authenticating to GCR..." >&2
gcloud docker --authorize-only

# re-tag images with "latest" and push those too
for dockerfile in $(ls -X ${RESOURCES_HOME}/Dockerfile.*|grep -v ".local"); do

    IMAGE_NAME=$(echo "${dockerfile}" | sed "s/.*\/Dockerfile\.\(.\+\)$/\1/g")
    IMAGE_NAME=${IMAGE_NAME//_/-}

    echo "Re-tagging Docker image '${TAG_PREFIX}-${IMAGE_NAME}:${TAG}'..." >&2
    docker tag "${TAG_PREFIX}-${IMAGE_NAME}:${TAG}" "${TAG_PREFIX}-${IMAGE_NAME}:latest"
    docker push "${TAG_PREFIX}-${IMAGE_NAME}:latest"
done

# re-tag main deployster image with "latest" and push that too
echo "Re-tagging main Docker image..." >&2
docker tag "${TAG_PREFIX}:${TAG}" "${TAG_PREFIX}:latest"
docker push "${TAG_PREFIX}:latest"
