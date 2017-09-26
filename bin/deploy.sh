#!/usr/bin/env bash

# if GCP_SA_JSON is provided, use it to activate the service account it references
if [[ -n "${GCP_SA_JSON}" ]]; then

    # store it in a temporary file
    GCP_SA_JSON_FILE="/tmp/gcp_service_account.json"
    GOOGLE_APPLICATION_CREDENTIALS="${GCP_SA_JSON_FILE}"
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
fi
echo "Google Cloud SDK will use GCP account: $(gcloud info --format=json | jq -r '.config.account')" >&2

# proceed to actual deployment
GOOGLE_APPLICATION_CREDENTIALS="${GOOGLE_APPLICATION_CREDENTIALS}" PYTHONUNBUFFERED=1 exec $(dirname $0)/apply.py $@
