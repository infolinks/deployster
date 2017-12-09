#!/usr/bin/env bash

set -e

docker build -q --file ./Dockerfile.test --tag infolinks/deployster:testing .
docker run --tty infolinks/deployster:testing
