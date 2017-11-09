#!/usr/bin/env bash

TAG="${1}"
[[ -z "${TAG}" ]] && echo "usage: $0 <tag>" && exit 1

set -ex

sed -i "s/^FROM .*/FROM gcr.io\/infolinks-gcr\/deployster-gcp-base:${TAG}/g" ./resources/gcp/compute/address/Dockerfile
sed -i "s/^FROM .*/FROM gcr.io\/infolinks-gcr\/deployster-gcp-base:${TAG}/g" ./resources/gcp/container/cluster/Dockerfile
sed -i "s/^FROM .*/FROM gcr.io\/infolinks-gcr\/deployster-gcp-base:${TAG}/g" ./resources/gcp/project/Dockerfile

gcloud docker -- build --tag "gcr.io/infolinks-gcr/deployster-gcp-base:${TAG}" --file "./resources/gcp/base/Dockerfile" ./resources
gcloud docker -- build --tag "gcr.io/infolinks-gcr/deployster-gcp-compute-address:${TAG}" --file "./resources/gcp/compute/address/Dockerfile" ./resources
gcloud docker -- build --tag "gcr.io/infolinks-gcr/deployster-gcp-container-cluster:${TAG}" --file "./resources/gcp/container/cluster/Dockerfile" ./resources
gcloud docker -- build --tag "gcr.io/infolinks-gcr/deployster-gcp-project:${TAG}" --file "./resources/gcp/project/Dockerfile" ./resources

if [[ "${2}" == "push" ]]; then
    gcloud docker -- push gcr.io/infolinks-gcr/deployster-gcp-base:${TAG}
    gcloud docker -- push gcr.io/infolinks-gcr/deployster-gcp-compute-address:${TAG}
    gcloud docker -- push gcr.io/infolinks-gcr/deployster-gcp-container-cluster:${TAG}
    gcloud docker -- push gcr.io/infolinks-gcr/deployster-gcp-project:${TAG}
fi
