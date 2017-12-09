#!/usr/bin/env bash

# parse arguments
TAG="${1}"
PUSH="${2}"

# validate arguments
[[ -z "${TAG}" ]] && echo "usage: $0 <tag>" >&2 && exit 1

# setup
DEPLOYSTER_HOME=$(cd $(dirname $0)/..; pwd)
RESOURCES_HOME="${DEPLOYSTER_HOME}/resources"
TAG_PREFIX="infolinks/deployster"
IMAGE_FROM_PATTERN="s/^FROM \(infolinks\/deployster-[^:]\+\):.\+$/FROM \1:${TAG}/g"

# fail on first error
set -e

# process Dockerfile files and replace ":local" in "FROM" clauses with actual tag
echo "Creating versioned Dockerfiles..." >&2
for dockerfile in $(ls -X ${RESOURCES_HOME}/Dockerfile.*|grep -v ".local"); do
    sed "${IMAGE_FROM_PATTERN}" "${dockerfile}" > "${dockerfile}.local"
done

# build resource images
for dockerfile in $(ls -X ${RESOURCES_HOME}/Dockerfile.*|grep -v ".local"); do
    IMAGE_NAME=$(echo "${dockerfile}" | sed "s/.*\/Dockerfile\.\(.\+\)$/\1/g")
    IMAGE_NAME=${IMAGE_NAME//_/-}
    echo ""
    echo ""
    echo "Building Docker image '${TAG_PREFIX}-${IMAGE_NAME}:${TAG}'..." >&2
    docker build --tag "${TAG_PREFIX}-${IMAGE_NAME}:${TAG}" --file "${dockerfile}.local" "${RESOURCES_HOME}"
done

# build deployster image
echo ""
echo ""
echo "Building Docker image '${TAG_PREFIX}:${TAG}'..." >&2
docker build --build-arg "VERSION=${TAG}" \
             --tag "${TAG_PREFIX}:${TAG}" \
             --file "${DEPLOYSTER_HOME}/Dockerfile" "${DEPLOYSTER_HOME}"

# push images (if asked to)
if [[ "${PUSH}" == "push" ]]; then

    echo "Authenticating to DockerHub..." >&2
    gcloud docker --authorize-only

    for dockerfile in $(ls -X ${RESOURCES_HOME}/Dockerfile.*|grep -v ".local"); do
        IMAGE_NAME=$(echo "${dockerfile}" | sed "s/.*\/Dockerfile\.\(.\+\)$/\1/g")
        IMAGE_NAME=${IMAGE_NAME//_/-}
        echo "Pushing Docker image '${TAG_PREFIX}-${IMAGE_NAME}:${TAG}'..." >&2
        docker push "${TAG_PREFIX}-${IMAGE_NAME}:${TAG}"
    done

    # push deployster image
    echo "Pushing Docker image '${TAG_PREFIX}:${TAG}'..." >&2
    docker push "${TAG_PREFIX}:${TAG}"
fi

exit 0
