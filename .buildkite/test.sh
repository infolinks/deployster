#!/usr/bin/env bash

set -e

docker build -q --file ./Dockerfile.test --tag infolinks/deployster:test-${BUILDKITE_COMMIT} .
docker run --env COVERALLS_REPO_TOKEN="${COVERALLS_REPO_TOKEN}" \
           --env BUILDKITE="${BUILDKITE}" \
           --env BUILDKITE_JOB_ID="${BUILDKITE_JOB_ID}" \
           --env BUILDKITE_BRANCH="${BUILDKITE_BRANCH}" \
           --tty infolinks/deployster:test-${BUILDKITE_COMMIT}