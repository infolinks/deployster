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

    echo "Re-tagging Docker image '${TAG_PREFIX}-${IMAGE_NAME}:${TAG}' to '${TAG_PREFIX}-${IMAGE_NAME}:latest'..." >&2
    docker tag "${TAG_PREFIX}-${IMAGE_NAME}:${TAG}" "${TAG_PREFIX}-${IMAGE_NAME}:latest"
    docker push "${TAG_PREFIX}-${IMAGE_NAME}:latest"
done

# re-tag k8s synonyms
echo "Re-tagging Kubernetes resources to the 'latest' tag..."
docker tag "${TAG_PREFIX}-${IMAGE_NAME}:${TAG}" "${TAG_PREFIX}-${IMAGE_NAME}:latest"
docker tag "infolinks/deployster-k8s-clusterrole:${TAG}" "infolinks/deployster-k8s-clusterrole:latest"
docker tag "infolinks/deployster-k8s-clusterrolebinding:${TAG}" "infolinks/deployster-k8s-clusterrolebinding:latest"
docker tag "infolinks/deployster-k8s-configmap:${TAG}" "infolinks/deployster-k8s-configmap:latest"
docker tag "infolinks/deployster-k8s-cronjob:${TAG}" "infolinks/deployster-k8s-cronjob:latest"
docker tag "infolinks/deployster-k8s-daemonset:${TAG}" "infolinks/deployster-k8s-daemonset:latest"
docker tag "infolinks/deployster-k8s-deployment:${TAG}" "infolinks/deployster-k8s-deployment:latest"
docker tag "infolinks/deployster-k8s-horizontalpodautoscaler:${TAG}" "infolinks/deployster-k8s-horizontalpodautoscaler:latest"
docker tag "infolinks/deployster-k8s-ingress:${TAG}" "infolinks/deployster-k8s-ingress:latest"
docker tag "infolinks/deployster-k8s-job:${TAG}" "infolinks/deployster-k8s-job:latest"
docker tag "infolinks/deployster-k8s-namespace:${TAG}" "infolinks/deployster-k8s-namespace:latest"
docker tag "infolinks/deployster-k8s-networkpolicy:${TAG}" "infolinks/deployster-k8s-networkpolicy:latest"
docker tag "infolinks/deployster-k8s-node:${TAG}" "infolinks/deployster-k8s-node:latest"
docker tag "infolinks/deployster-k8s-persistentvolume:${TAG}" "infolinks/deployster-k8s-persistentvolume:latest"
docker tag "infolinks/deployster-k8s-persistentvolumeclaim:${TAG}" "infolinks/deployster-k8s-persistentvolumeclaim:latest"
docker tag "infolinks/deployster-k8s-pod:${TAG}" "infolinks/deployster-k8s-pod:latest"
docker tag "infolinks/deployster-k8s-replicaset:${TAG}" "infolinks/deployster-k8s-replicaset:latest"
docker tag "infolinks/deployster-k8s-replicationcontroller:${TAG}" "infolinks/deployster-k8s-replicationcontroller:latest"
docker tag "infolinks/deployster-k8s-role:${TAG}" "infolinks/deployster-k8s-role:latest"
docker tag "infolinks/deployster-k8s-rolebinding:${TAG}" "infolinks/deployster-k8s-rolebinding:latest"
docker tag "infolinks/deployster-k8s-secret:${TAG}" "infolinks/deployster-k8s-secret:latest"
docker tag "infolinks/deployster-k8s-service:${TAG}" "infolinks/deployster-k8s-service:latest"
docker tag "infolinks/deployster-k8s-serviceaccount:${TAG}" "infolinks/deployster-k8s-serviceaccount:latest"
docker tag "infolinks/deployster-k8s-statefulset:${TAG}" "infolinks/deployster-k8s-statefulset:latest"
docker tag "infolinks/deployster-k8s-storageclass:${TAG}" "infolinks/deployster-k8s-storageclass:latest"

# re-tag main deployster image with "latest" and push that too
echo "Re-tagging main Docker image..." >&2
docker tag "${TAG_PREFIX}:${TAG}" "${TAG_PREFIX}:latest"
docker push "${TAG_PREFIX}:latest"
