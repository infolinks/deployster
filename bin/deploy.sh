#!/usr/bin/env bash

# obtain GCP service account JSON contents from environment variable
if [[ -z "${GCP_SA_JSON}" ]]; then
    echo "please provide the 'GCP_SA_JSON' environment variable" >&2
    echo "example: docker run -e GCP_SA_JSON=\$(cat my-sa-key.json) infolinks/deployster <arguments...>" >&2
    exit 1
fi

# store it in a temporary file
GCP_SA_JSON_FILE="/tmp/gcp_service_account.json"
echo -nE "${GCP_SA_JSON}" > ${GCP_SA_JSON_FILE}
if [[ $? != 0 ]]; then
    echo "failed writing service account JSON file to '${GCP_SA_JSON_FILE}'"
    exit 1
fi

# activate the service account
gcloud auth activate-service-account --key-file=${GCP_SA_JSON_FILE}
if [[ $? != 0 ]]; then
    echo "failed activating service account from JSON file at '${GCP_SA_JSON_FILE}'" >&2
    echo "JSON file contents:" >&2
    cat ${GCP_SA_JSON_FILE} >&2
    exit 1
fi

# proceed to actual deployment
exec $(dirname $0)/apply.py $@
