#!/usr/bin/env bash

TAG="${1}"
[[ -z "${TAG}" ]] && echo "usage: $0 <tag> <version>" >&2 && exit 1

VERSION="${2}"
[[ -z "${VERSION}" ]] && echo "usage: $0 <tag> <version>" >&2 && exit 1

set -ex

gcloud docker -- tag "gcr.io/infolinks-gcr/deployster-gcp-base:${TAG}" "infolinks/deployster-gcp-base:${VERSION}"
gcloud docker -- tag "infolinks/deployster-gcp-base:${VERSION}" "infolinks/deployster-gcp-base:latest"
gcloud docker -- push "infolinks/deployster-gcp-base:${VERSION}"
gcloud docker -- push "infolinks/deployster-gcp-base:latest"

gcloud docker -- tag "gcr.io/infolinks-gcr/deployster-gcp-compute-address:${TAG}" "infolinks/deployster-gcp-compute-address:${VERSION}"
gcloud docker -- tag "infolinks/deployster-gcp-compute-address:${VERSION}" "infolinks/deployster-gcp-compute-address:latest"
gcloud docker -- push "infolinks/deployster-gcp-compute-address:${VERSION}"
gcloud docker -- push "infolinks/deployster-gcp-compute-address:latest"

gcloud docker -- tag "gcr.io/infolinks-gcr/deployster-gcp-container-cluster:${TAG}" "infolinks/deployster-gcp-container-cluster:${VERSION}"
gcloud docker -- tag "infolinks/deployster-gcp-container-cluster:${VERSION}" "infolinks/deployster-gcp-container-cluster:latest"
gcloud docker -- push "infolinks/deployster-gcp-container-cluster:${VERSION}"
gcloud docker -- push "infolinks/deployster-gcp-container-cluster:latest"

gcloud docker -- tag "gcr.io/infolinks-gcr/deployster-gcp-project:${TAG}" "infolinks/deployster-gcp-project:${VERSION}"
gcloud docker -- tag "infolinks/deployster-gcp-project:${VERSION}" "infolinks/deployster-gcp-project:latest"
gcloud docker -- push "infolinks/deployster-gcp-project:${VERSION}"
gcloud docker -- push "infolinks/deployster-gcp-project:latest"
