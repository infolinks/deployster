# Quick start

This page will help you get up & running with Deployster with a short
tutorial (roughly 5 to 10 minutes, honest!).

You will need the following before you can run the examples in this
tutorial:

- [Google Cloud Platform][1] account (no AWS yet, sorry!)
- [Google Cloud SDK][2] installed and authenticated on your machine
- [Docker][3] installed on your machine

## Preface

Some common ground before we start:

### Goals

The goals of this tutorial will be:

- Generate a GCP service account that Deployster will use when
interacting with GCP (ensures that Deployster will not be able to
perform actions you do not want to allow it to do).

- Write a deployment manifest that will simply create a static IP
address in GCP.

### Conventions

- `GCP` will be used as a short-hand for _Google Cloud Platform_.

### Execution

Instructions in this tutorial are provided as `bash` commands. Some
commands will create `bash` variables (eg. `MY_VAR=value`), and its
common that later commands in the document will rely on earlier such
variables (eg. `echo $MY_VAR` later in the document relies that you
ran `MY_VAR=value` earlier in the same `bash` session). It's therefor
recommended that you perform the entire tutorial in the same `bash`
session, to avoid repetition.

## GCP Service account

It's a good practice to perform GCP actions (especially for deployment)
using a dedicated service account, as this allows you to restrict the
permissions for that account, revoke its authentication keys, etc.

While generating a GCP service account & its credentials is outside the
scope of this tutorial, here is a short script to help with it: (please
ensure that `gcloud` is working and authenticated before running this
script!)

```bash
DEPLOYSTER_SA_NAME="deployster"
DEPLOYSTER_SA_FILE="./deployster-sa.json"

# infer your GCP project name:
GCP_PROJECT=$(gcloud info --format='value(config.project)')

# create the deployster service account:
gcloud iam service-accounts create ${DEPLOYSTER_SA_NAME} \
    --project=${GCP_PROJECT} \
    --display-name ${DEPLOYSTER_SA_NAME}

# find the service account's Email address
DEPLOYSTER_SA_EMAIL=$(gcloud iam service-accounts list \
    --project=${GCP_PROJECT} \
    --filter="displayName:${DEPLOYSTER_SA_NAME}" \
    --format='value(email)')

# make the service account an owner of the project
# (you would probably want to change this...)
gcloud projects add-iam-policy-binding $GCP_PROJECT \
    --role roles/owner \
    --member serviceAccount:${DEPLOYSTER_SA_EMAIL}

# download a JSON credentials file for the account:
gcloud iam service-accounts keys create ./deployster-sa.json \
    --iam-account ${DEPLOYSTER_SA_EMAIL}
```

## Deployment manifest

Now lets write our _deployment manifest_. This file will contain the
definition of all the resources that we want Deployster to verify &
deploy. Note that in real-world scenario you will probably want to
break this file into multiple files (eg. `machines.yaml`, `cluster.yaml`
and so on).

Lets create a file callled `tutorial-manifest.yaml` by running this
`bash` command:

```bash
cat > ./tutorial-manifest.yaml <<EOT
plugs:
  gcp-service-account:
    path: "${DEPLOYSTER_SA_FILE}"
    read_only: true
  
resources:
  
  my-ip-address:
    type: infolinks/deployster-gcp-compute-ip-address
    config:
      project_id: "${GCP_PROJECT}"
      name: tutorial-ip
EOT
```

## Running

Running Deployster is easy - here's a `bash` snippet to do it:

```bash
curl -sSL -O "https://raw.githubusercontent.com/infolinks/deployster/master/deployster.sh"
./deployster.sh ./tutorial-manifest.yaml
```

If all went as planned, you should see the following output:

```log
TBD.
```

[1]: https://cloud.google.com/
[2]: https://cloud.google.com/sdk/downloads#interactive
[3]: https://docs.docker.com/engine/installation/
