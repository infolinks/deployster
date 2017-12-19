# Introduction

Deployster is an extensible resource-centric deployment tool. It works
by enabling deployers (eg. _You!_) to declare the _desired_ state of the
deployment topology, discovers the topology's _current_ state, and then
attempts to migrate it from the _current_ state to the _desired_ state.

The main differences between Deployster and other, similar, tools (such
as [Google Deployment Manager][1], [Terraform][2], and others) are:

- **Docker-first philosophy**: resource types (eg. VMs, IP-addresses, disks,
etc) are written as Docker images, allowing them to be reused in any
deployment, on any platform.

- **Highly extensible**: since resource implementations are merely Docker
images - you can create new resource types by creating your own Docker
images, using any technology you want. Want to create a new resource
that represents a GitHub repository using Ruby? Done. Just implement a
new Docker image and write your source code in Ruby inside the image,
then use that resource in any Deployster manifest. The Docker image name
& tag represent the resource type.

- **Stateless**: in contrast to similar tools, Deployster will never store
your topology state (locally or remotely) which enables your to also
work on your infrastructure & deployments manually or in other tools,
side-by-side with Deployster. While we are aware that this might incurr
a performance penalty at times (for state discovery) we believe this is
preferrably to a _wrong state discovery_.

- **Reproducible**: deployments are meant to be idempotent, such that
running the same deployment multiple times should yield the same result
as running it just once, assuming that nothing else modified the state.

### Getting started & documentation

The [quick start](./quickstart) page will get you up & running in 10
minutes. For a more in-depth overview of Deployster, head over to the
[overview](./overview) page to learn more about the core concepts in
Deployster.

<aside class="warning">
The documentation is still in its early phases. Some of the information
may be a bit out of date or inaccurate. We are sorry for this temporary
state and hope to finish documenting Deployster soon!
</aside>

### Credits

Deployster was written by the team @ Infolinks as a means to improve
our deployment process. We plan to gradually open source more & more
components of that pipeline in the coming months.

[1]: https://cloud.google.com/deployment-manager/docs/configuration/supported-resource-types    "Google Deployment Manager"
[2]: https://www.terraform.io/docs/providers/external/data_source.html                          "Terraform"
[3]: http://jinja.pocoo.org/                                                                    "Jinja2"