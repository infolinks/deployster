# deployster

[![Build status](https://badge.buildkite.com/b085786cdaac1f36a044eb99de470c4b8815a4ccd92281967c.svg)](https://buildkite.com/infolinks/infolinks-slash-deployster-ci)

Deployster is an extensible resource-centric deployment tool. It allows
developers to declare their _desired_ state of the deployment plane &
toplogy, and then attempts to migrate from the _current_ state into the
_desired_ state.

The difference between Deployster and other similar tools such as
[Google Deployment Manager](https://cloud.google.com/deployment-manager/docs/configuration/supported-resource-types),
[Terraform](https://www.terraform.io/docs/providers/external/data_source.html) and
others is its extensibility:

- Extensible: new resource types can be easily added
- Docker-first philosophy: resources are written as Docker images, which
allows resource implementors to use any tool they deem appropriate
- Stateless: in contrast to similar tools, Deployster will never store
your topology state (locally or remotely) which enables your to work on
your infrastructure or deployments manually, side-by-side with Deployster.
- Reproducible: deployments are meant to be idempotent, such running the
same deployment multiple times should yield the same result as running
it just once, assuming that nothing else modifies it.
- Smart: Deployster allows (and sometimes requires) inter-resource
dependencies, which enable Deployster to roll out actions in the
appropriate order.
- Safe: everyone makes mistakes, and nobody likes dealing with them at
midnight :)
    - Deployster attempts to help by being fully transparent about
    what it is about to do and what it actually does.
    - Will support _Rollbacks_ which will enable you to more easily
    recover from accidental roll-outs.

## Architecture

Deployster mechanics is built around three main components:

- Resource Types: each resource type is essentially a Docker image that
implements a simple contract that allows receiving configuration,
querying the resource state, and performing an action.

- Manifest: a YAML or JSON document (TBD) written by the
deployer or developer, that describes _how_ the final state should be.
It's Deployster's job to use this manifest to _discover_ the current
state, and then plan the set of actions that will migrate it to the
_desired_ state as described in the manifest.

- Context: a separate set of YAML or JSON documents that configure
the deployment. Since you would usually want to use the same deployment
manifests for different environments (eg. QA, production, etc) or
scenarios, there will always be dynamic aspects of the manifests (eg.
the amount of CPUs or RAM for a VM). The context, by virtue of being
dynamic, allow extracting this information from the manifest. You
typically control the context by choosing different context files to
attach to the deployment.

## Resource graph

The first thing Deployster will do is build an up-to-date resource graph
which reflects the current deployment state. It will collect all
resources from the manifest, and query each one for its current state.
Resources that depend on other resources will wait until those resources
are queried first, but will still be queried, even if the resources they
depend on do not exist.

The response from resources to the state query must also include the
list of actions required.

## Context

TBD.

## Requirements & Plugs

TBD.

## Resource Types

TBD.

## Python dependencies

* PyYAML
