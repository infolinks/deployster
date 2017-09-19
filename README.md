# deployster

[![Build Status](https://travis-ci.org/infolinks/deployser.svg?branch=master)](https://travis-ci.org/infolinks/deployster)

Deployster is an opinionated deployment tool, tying together deployment
configuration, GCE assets and GKE manifests to a full, reproducible
deployment.

## Methodology

Deployster aims to unify and tie together a typical Kubernetes deployment
sequence with an opinionated view of how to progress from an actual
state to the desired state, strictly maintaining an **idempotent** workflow
that enables reproducible and consistent deployments.

The deployment sequence is composed of the following stages: (see below
for a description of each stage)

1. Target GCP project setup - generating and configuring a target GCP
project.

2. Build a unified environment context, out of multiple, ordered, JSON
files.

3. Apply a sequence of [Google Deployment Manager](https://cloud.google.com/deployment-manager/docs/)
(GDM) configurations.

4. Apply a sequence of [Kubernetes](https://kubernetes.io) configuration
maps & manifests onto the Kubernetes cluster (if any).

This sequence is designed to be idempotent, such as executing a
deployment with the same environment & configuration should always yield
the same result.

### Target GCP project setup

Resources will eventually have to be deployed into a GCP project.
Deployster will automatically ensure that:

1. The target project exists, or create it if not - under your GCP
organization.

2. Ensure that the project is associated with your Google billing
account.

3. Ensure that Google Deployment Manager API is enabled.

4. Ensure that Google Logging API is enabled (for Stackdriver logging,
mainly for the Kubernetes cluster).

5. Ensure that Google Monitoring API is enabled (for Stackdriver's
Kubernetes monitoring mainly).

6. Ensure that the possibly-new GCP project's default compute service
account has the `Storage Viewer` IAM role in your [Google Container Registry](https://cloud.google.com/container-registry/)
project.

Having such a process builtin makes Deployster very powerful due to the
fact that you no longer have to manually set up distinct development or
QA environments. Moreover, since the logic for creating these
environments is embedded in Deployster and your configuration files,
you can have environments that are almost identical to your production
environment (with slight modifications in your dev/QA-specific JSON
files, eg. smaller number of nodes in your cluster, use zones that are
closer to the physical location of your development office, etc).

### The Environment Context

Deployster expects a list of JSON files upon execution. Those files are
then merged (in the same order you provided them) to generate a unified
JSON document - called _the environment_, or _the environment context_.
This environment is used as a context for post-processing all your GDM
& Kubernetes manifests, using the [Jinja2](http://jinja.pocoo.org/)
templating engine.

This enables making your GDM configurations & Kubernetes manifests
dynamic - eg. setting the zone of a VM from a configuration value in the
environment.

For example, this GDM configuration creates a Google Compute Engine
static IP address named `my-static-ip-address` in a region specified in
the environment JSON key `myapp.geo.region`:

    - name: my-static-ip-address
      type: compute.v1.address
      properties:
        region: {{ myapp.geo.region }}

Here's one of the environment JSON files:

    {
        // various properties here

        "myapp": {
            "geo": {
                "region": "us-east1"
            }
        }

        // various properties here
    }

### Google Deployment Manager

GDM deployments, albeit a very generic name, are really aliases to Google
Deployment Manager manifest files, where each `YAML` file is a single
"deployment". To avoid confusion with a deployment process, we'll call
these files (the _Google Deployment Manager's Deployments_) as GDM
manifests.

Each such manifest is a `YAML` file, located under the `deployments`
directory, that describes a set of resources that need to be present in
the target environment, like VMs, IP addresses, TLS certificates, etc.
These `YAML` files are submitted to Google Deployment Manager upon
deployment for processing.

Note that Deployster, however, will not simply deploy all `YAML` files
in the `deployments` directory - instead it will obtain the list of GDM
manifests to deploy from the environment context. The way to specify the
list of GDM manifests in your environment context is like this:

    {
        ...
        "gdm": {
            "defaultStrategy": "update_if_changed",
            "configurations": [
                {
                    "name": "certificates"
                },
                {
                    "name": "cluster",
                    "strategy": "create_only"
                },
                {
                    "name": "weave-scope"
                }
            ]
        },
        ...
    }

You can see that the `gdm.configurations` JSON path is an array of JSON
objects, each one denoting a single GDM manifest to be deployed. For
each such manifest, we specify the name (which will be translated to a
GDM manifest filename under the `deployments` directory) and optionally
a deployment strategy (see below). If no deployment strategy is given,
the `gdm.defaultStrategy` property is used, or if it's missing - the
default strategy is `update_if_changed`.

Specifying the list of GDM manifests to be deployed in your environment
context has the benefit of applying different manifests to different
environments - for example, you could create special manifests that are
only meant to be deployed in development or QA environments that
restrict access to your machines.

#### Deployment strategy

Some deployments in Google Deployment Manager require a different
strategy than the simple _desired vs. actual_ resolve process - eg. when
the deployment updates resources that Google Deployment Manager does not
support updates for (eg. Kubernetes clusters). For such deployments, a
conditional _drop then create_ (aka. _"recreate"_) strategy is more
appropriate than the default _"update"_ strategy, or alternatively a
_only create_ strategy will create the resource once, and never touch it
again (you wouldn't want to drop & create the cluster in production now
would ya?)

The available strategies are:

* The `update_always` strategy always submit the configuration to Google
  Deployment Manager, letting it create any missing resources, delete
  resources that are no longer present in the configuration, and update
  resources whose configuration changed.

* The `update_if_changed` strategy is the same as `update_always`, but
  compares the configuration file contents to the currently stored copy
  of the configuration in the Google Deployment Manager repository, and
  only if they differ it will be submitted to Google Deployment Manager.
  *This is the default mode*.

* The `create_only` strategy will deploy the manifest if it has not yet
  been deployed. Otherwise, if it exists it will leave it alone.

* The `recreate` strategy is similar to `update_always` in that it
  compares the file contents to the previously deployed one, but if
  there's a difference, it will _*delete*_ the deployment first (**causing
  any resources it previously created to be deleted as well!**) and then
  create the deployment from scratch (hence the name "recreate").

### Kubernetes

[Kubernetes](https://kubernetes.io) is a "_Production-Grade Container
Orchestration_" framework, intended to host applications and processes
that are kept running automatically, with support for common
architectural needs such as service discovery & load-balancing,
isolation, manual & automatic scaling, etc.

Deployment to Kubernetes clusters is performed using the `kubectl` tool
which interacts with Kubernetes clusters for querying, administration &
deployment. The input to this tool is a set of `YAML` files that
describe the _desired state_ of resources that should be deployed in the
cluster (such as configurations, pods, services, etc). The tool detects
the _actual state_ of those resources, and then performs the necessary
actions required to reach the _desired state_ from the _actual state_.

Note that the creation of the actual cluster should be done _before_
using this tool - in our case, using the Google Deployment Manager. Once
a cluster exists, we can use this tool to deploy or update resources in
it.

The deployment process is applying Kubernetes configuration maps and
manifests onto the Kubernetes cluster using manifests under the
`kubernetes` directory. This directory contains the following sections:

* The `security` directory contains manifests that apply required
  security bindings necessary for deployment (both for this project and
  for developers at large.)

* The `system` directory contains configuration maps and manifests
  intended to be deployed into the `kube-system` namespace. These are
  infrastructure manifests that are not an intrinsic part of any
  application.

* Any other directory contains configuration maps and manifests that
  should be deployed into a separate namespace (whose name is the name
  of this sub-directory). We recommend creating a `app` sub-directory
  and placing all your apps there. This provides a good enough isolation
  between system resources (in `kube-system` namespace) and applicative
  resources (in the `app` namespace)

The deployment process will deploy these three sections in the order
specified above.

Each manifest is treated as a [Jinja2](http://jinja.pocoo.org/docs/2.9/)
template, just as described for the Google Deployment Manager
configuration files in the previous section. Therefor a manifest can
reference configuration values from the environment context, allowing
the manifest to contain dynamic per-environment values.

## Contributions

Any contribution to the project will be appreciated! Whether it's bug
reports, feature requests, pull requests - all are welcome, as long as
you follow our [contribution guidelines for this project](CONTRIBUTING.md)
and our [code of conduct](CODE_OF_CONDUCT.md).

### Local development

For developers, in order to set up a development environment for this
project, please follow these instructions:

1. Install Python 2.7.x

2. Ensure you have the `virtual` package

    If you're on `Fedora`, you can run this:

        sudo dnf install python2-virtualenv

    Otherwise, use `pip`:

        pip install --upgrade virtualenv

    See [virtualenv](https://virtualenv.pypa.io/en/stable/) for more
    information.

3. Create or activate a virtualenv in `python` by running this at the
   repository root:

        virtualenv .python2.7
        source ./.python2.7/bin/activate
        pip install jsonmerge Jinja2 google-api-python-client

    **NOTE:** the last step (`pip install ...`) is a one time step, so
    once you've created the virtual environment and executed the `pip`
    step, you no longer need to run it again (unless you deleted the
    `.python2.7` directory of course).

4. Ensure you're authenticated to `gcloud`:

        gcloud auth application-default login

    [See here](https://cloud.google.com/sdk/gcloud/reference/auth/application-default/login) for more information.

5. Deploy! Execute this in the repository root:

        PYTHONUNBUFFERED=1 ./bin/apply.py ...

    For example:

        PYTHONUNBUFFERED=1 ./bin/apply.py \
                --org-id 123 \
                --billing-account-id 321 \
                --gcr-project my-gcr-project \
                --project my-qa-project \
                --env qa \
                default.json qa.json

    This will deploy to the `qa` environment, which will reside in the
    `my-qa-project` GCP project, but will make sure that the default
    service account in `my-qa-project` will have access to GCR in the
    `my-gcr-project` (so Kubernetes will be able to pull Docker images
    from it). The environment context for this deployment will be
    created by layering `qa.json` on top of `default.json` (so `qa.json`
    will override values in `default.json`).

## ROADMAP

* Support touching Kubernetes deployments when configmaps change, so they
  are restarted to take the new configuration into effect.
