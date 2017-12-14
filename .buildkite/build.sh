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

# create k8s docker image aliases
echo "Building Docker images for Kubernetes resources..." >&2
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-clusterrole:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-clusterrolebinding:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-configmap:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-cronjob:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-daemonset:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-deployment:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-horizontalpodautoscaler:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-ingress:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-job:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-namespace:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-networkpolicy:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-node:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-persistentvolume:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-persistentvolumeclaim:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-pod:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-replicaset:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-replicationcontroller:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-role:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-rolebinding:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-secret:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-service:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-serviceaccount:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-statefulset:${TAG}"
docker tag "infolinks/deployster-k8s:${TAG}" "infolinks/deployster-k8s-storageclass:${TAG}"

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
