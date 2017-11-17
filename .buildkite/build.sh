#!/usr/bin/env bash

TAG="${1}"
[[ -z "${TAG}" ]] && echo "usage: $0 <tag>" >&2 && exit 1

for docker_file in $(find "./resources" -name "Dockerfile"); do
    sed "s/^FROM \([^:]\+\):.+$/FROM \1:${TAG}/g" "${docker_file}" > ${docker_file}.local
done

# build a Docker image from the given path
function build_image(){
    IMAGE_PATH="${1}"
    IMAGE_NAME="infolinks/deployster/${IMAGE_PATH}"
    docker build --tag "${IMAGE_NAME}:${TAG}" --file "./resources/${IMAGE_PATH}/Dockerfile.local" ./resources
    if [[ "${2}" == "push" ]]; then
        docker push "${IMAGE_NAME}:${TAG}"
    fi
}

set -e

# authenticate to GCR & build images
gcloud docker --authorize-only
build_image "gcp/base"
build_image "gcp/compute/address"
build_image "gcp/container/cluster"
build_image "gcp/project"
build_image "k8s/base"
build_image "k8s/namespace"
#build_image "k8s/rbac/cluster-role"
#build_image "k8s/rbac/role"
build_image "k8s/rbac/service-account"
