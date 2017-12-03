# Quick start

To quickly get up & running with the examples in this repository, you
will need the following:

- Google Cloud Platform account
- [Docker][1] installed on your machine
- [Google Cloud SDK][2] installed on your machine and authenticated to
your GCP account.

## Setup

You would usually want to run Deployster under a dedicated service
account, usually as part of a continuous delivery cycle. Here's a quick
& dirty script to generate a service account & its credentials file:

```bash
DEPLOYSTER_SA_NAME=deployster

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
gcloud projects add-iam-policy-binding $GCP_PROJECT \
    --role roles/owner \
    --member serviceAccount:${DEPLOYSTER_SA_EMAIL}

# enable the account to manage your billing account (so it can create new projects under it)
# NOTE: this is simply for demonstration purposes, we don't recommend doing this in a real environment.
gcloud projects add-iam-policy-binding $GCP_PROJECT \
    --role roles/billing.admin \
    --member serviceAccount:${DEPLOYSTER_SA_EMAIL}

# download a JSON credentials file for the account:
gcloud iam service-accounts keys create ./deployster-sa.json \
    --iam-account ${DEPLOYSTER_SA_EMAIL}
```

Deployster supports automatically reading some variable files in
specific locations (current directory & `~/.deployster`) that are named
`vars[.*].auto.yaml`. Lets create one with some variables that our
example manifest uses:

```bash
# create a context file with variables for the deployment manifest:
cat > ./vars.auto.yaml <<EOT
gcp_service_account_json_file: "./deployster-sa.json"
gcp_project: "<your_gcp_project_id>"
organization_id: <your_gcp_organization_numeric_id>
billing_account_id: "<your_billing_account_id>"
zone: "europe-west1-c"
kube_path: "/some/absolute/path/for/k8s"
test_admin_user: ${DEPLOYSTER_SA_EMAIL}
EOT
```

The examples we want to run are in the deployster GitHub repository -
lets clone it:

```bash
# clone the deployster repository (for the demo, not required in real-world)
git clone git@github.com:infolinks/deployster
cd deployster/examples
```

## Running

Now lets run one of the manifests:

```bash
../deployster.sh ./cluster.yaml
```

## Notes

This example grants wide permissions to the service account you are
creating. While this is fine for demonstration purposes, you would
probably grant a more narrow set of permissions to your service account
in real world usage. Keep in mind that the actual set of permissions
required is essentially derived from the type of resources you will be
deploying. For instance, you would not need to grant GKE permissions if
you're not using Kubernetes.

[1]: https://docs.docker.com/engine/installation/
[2]: https://cloud.google.com/sdk/downloads#interactive
