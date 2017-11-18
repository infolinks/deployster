#!/usr/bin/env bash

PY_VERSION=$(python --version 2>&1 | cut -d' ' -f2)
if [[ ! ${PY_VERSION} =~ 3.* ]]; then
    echo "${PY_VERSION} is too old." >&2
    exit 1
fi

BIN_DIR=$(cd $(dirname $0); pwd)
SRC_DIR=$(cd ${BIN_DIR}/../src; pwd)

PYTHONPATH="${SRC_DIR}:$PYTHONPATH"
exec python ${SRC_DIR}/deployster.py $@
