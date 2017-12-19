# Overview

Deployster mechanics is built around these core concepts:

- **Manifest**: a YAML document written by the deployer (eg. You!) that
describes _what_ the final state should be.

- **Context**: a shared set of variables that can be referenced in
resources defined in the manifest(s). These variables can be provided
dynamically from the commandline or from a YAML variables file.

- **Resources**: resources specified in the deployment manifest are
_typed_ - eg. a VM, disk, IP address, etc. Each resource type is backed
by a Docker image that handles discovery & updates for resources of its
type. For example, there's a Deployster _GCP Project_ image that knows
how to search for, create or update GCP projects.

- **Plugs**: a set of shared files or directories that can be used by
resources to share state. Each resource type can request one or plugs
from Deployster, and the deployer needs to satisfy those requirements.

However, the most important aspect of Deployster is understanding what
we call _the deployment lifecycle_ which is a bunch of fancy words to
describe the different phases that Deployster walks through as it reads
your manifests, discovers their state, and applies the relevant actions
to them. However, it would be hard understand the lifecycle without
first understanding the different entities that participate in it - so
here are those main entities:

## Manifest

The manifest represents the _desired_ state of your deployment topology.
It's comprised of a set of _resources_, potentially with inter-dependencies
between them, and a configuration clause for each resource that dictate
the various properites of that resource.

Each resource has a _type_ - which tells Deployster which component is
in charge of discovering the current resource's state, and also applying
any necessary _actions_ that should migrate it from its _current_ state
to the _desired_ state. Each resource type is a Docker image that
Deployster will run with instructions on what it wants the image to do
(discover state, create, etc).

Manifests are written in YAML files, and contain definitions of _plugs_
(see below) and _resources_. Here's an example manifest file:

```yaml
plugs:
  some_plug:
    path: ./some/local/path
    
resources:
  my_ip_address:
    type: infolinks/deployster-gcp-compute-ip-address
    config:
      project_id: my_gcp_project
      name: static-ip
```

This manifest declares a plug called `some_plug` and a resource called
`my_ip_address` whose type is `infolinks/deployster-gcp-compute-ip-address`.
You probably noticed that the resource type looks suspiciously similar
to a Docker image format - that's because it is! When Deployster runs,
it will use this Docker image to request discovery of the IP address's
state, and to create/update it if necessary.

<aside class="notice">
Note that you can split your deployment topology into multiple manifest
files - each describing a group of inter-related resources.
</aside>

## Context

The context is simply a set of variables that can be used in the
manifests. Variables are useful when there are certain aspects in your
resource configurations that you want to maintain externally from the
actual manifest files. For example, suppose you declare a GCP disk
resource in your manifest file, but the size of the disk is different,
based on the environment you deploy to - you can accomplish this using
variables, as follows:

```yaml
resources:
  my_disk:
    type: infolinks/deployster-gcp-compute-disk
    config:
      project_id: my_gcp_project
      name: data-disk
      size: '{{ data_disk_size }}'
```

When running Deployster, you can simply add `--var data_disk_size=15gb`
and your disk size would be 15GB.

Variables are populated from the following sources:

- The `--var` flag
- The `--var-file` flag which accepts a YAML file contain your variables.
- Automatic variables named `vars[.*].auto.yaml` in the current directory
and/or at `~/.deployster`.

## Resources

Resources are what it's all about in Deployster. Each resource is
composed of the following components:

- Name: each resource must be uniquely named
- Type: think VM, disk, IP, etc. In essence, this is actually the name
of the Docker image that handles resources of this type.
- Configuration: this is the heart of a resource definition - the set of
parameters that specify the desired state of the resource. For a VM, for
instance, this would be its CPU type, cores, RAM, etc. For a disk, this
would probably contain the disk size, whether it's SSD or not, etc. The
set of allowed properties is decided by the resource type.

Resource types (the Docker image) must obey a strict, yet simple,
protocol of communications between it and Deployster. As part of this
communication, the resource type will receive the resource configuration
and will be able to dictate what actions are necessary to bring the
resource from the current state to the desired state as declared in the
manifest.

The fact that resource types are simply Docker images, allows resource
types to be written in any language or technology - be it `bash`,
`python`, `ruby` or any other language of choice.

## Plugs

Plugs are the means by which different resources can share state between
them (with the permission of the deployer). Each plug is simply a file
or directory on the host machine, that can be _mounted_ to the relevant
resource type (a Docker image, rememebr?).

What determines whether a certain plug gets mounted to a certain
resource type is if the following two conditions are met:

- The resource type must _request_ this plug (based on its name)
- If the plug was defined as read-only (yes, you can do that!) then,
it will only be mounted if the resource type requested the plug as such.

If so, then when the resource type is run, the plug's file or directory
is mounted to it.

## What next?

The following articles are a good place to go next:

- [Quick start](./quickstart) in case you haven't read that yet
- [Writing manifests](./manifests) is a more in-depth article on the
available manifest syntax, options and best practices.
- [Managing the context](./context) explains more on when & how to
define variables, and how the context is built.
- [Deployment lifecycle & protocol](./lifecycle) provides a good
overview of how Deployster progresses through the phases of a deployment
as well as the underlying _resource protocol_ that defines how
Deployster and the _resource types_ communicate between them. Reading
this enable you to create new resource types.
- [Builtin resources](./builtin-resources) is the maintained list of
resources that Deployster is pre-packaged with. It's still small, but
we plan to grow this over time.
