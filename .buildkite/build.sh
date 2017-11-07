#!/usr/bin/env bash

set -ex

TAG="${BUILDKITE_COMMIT:=local}"

sed -i "s/^FROM .*/FROM gcr.io\/infolinks-gcr\/deployster-gcp-base:${TAG}/g" ./resources/gcp/compute/address/Dockerfile
sed -i "s/^FROM .*/FROM gcr.io\/infolinks-gcr\/deployster-gcp-base:${TAG}/g" ./resources/gcp/project/Dockerfile

docker build --tag "gcr.io/infolinks-gcr/deployster-gcp-base:${TAG}" --file "./resources/gcp/base/Dockerfile" ./resources
docker build --tag "gcr.io/infolinks-gcr/deployster-gcp-compute-address:${TAG}" --file "./resources/gcp/compute/address/Dockerfile" ./resources
docker build --tag "gcr.io/infolinks-gcr/deployster-gcp-project:${TAG}" --file "./resources/gcp/project/Dockerfile" ./resources
