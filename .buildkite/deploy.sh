#!/usr/bin/env bash

# small IntelliJ trick; will not actually run
if [[ 1 == 0 ]]; then
    BUILDKITE_COMMIT=${BUILDKITE_COMMIT}
    BUILDKITE_GITHUB_DEPLOYMENT_ENVIRONMENT=${BUILDKITE_GITHUB_DEPLOYMENT_ENVIRONMENT}
    BUILDKITE_GITHUB_DEPLOYMENT_TASK=${BUILDKITE_GITHUB_DEPLOYMENT_TASK}
    BUILDKITE_GITHUB_DEPLOYMENT_PAYLOAD=${BUILDKITE_GITHUB_DEPLOYMENT_PAYLOAD}
    BUILDKITE_BUILD_NUMBER=${BUILDKITE_BUILD_NUMBER}
fi

# validate configuration
[[ "${BUILDKITE_GITHUB_DEPLOYMENT_ENVIRONMENT}" != "production" ]] && echo "REJECTING: only 'production' deployment allowed for Infobot." && exit 1
[[ ${BUILDKITE_GITHUB_DEPLOYMENT_TASK} != buildkite:* ]] && echo "SKIPPING: task does not start with 'buildkite:'" && exit 0

# version
VERSION="$(echo "${BUILDKITE_GITHUB_DEPLOYMENT_PAYLOAD}" | jq -r '.version')-${BUILDKITE_BUILD_NUMBER}"
echo "Version:                       ${VERSION}" >> DEPLOYMENT

# setup aliases and bash flags (print commands, early-failure, and pipe failure)
set -exo pipefail

# tag & push image to DockerHub
gcloud docker -- tag gcr.io/infolinks-gcr/deployster:${BUILDKITE_COMMIT} infolinks/deployster:${VERSION}
gcloud docker -- tag gcr.io/infolinks-gcr/deployster:${BUILDKITE_COMMIT} infolinks/deployster:latest
gcloud docker -- push infolinks/deployster:${VERSION}
gcloud docker -- push infolinks/deployster:latest
