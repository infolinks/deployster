# Introduction

Deployster is an extensible resource-centric deployment tool. It works
by enabling deployers (eg. _You!_) to declare the _desired_ state of the
deployment topology, discovers the topology's _current_ state, and then
attempts to migrate it from the _current_ state to the _desired_ state.

The main differences between Deployster and other, similar, tools (such
as [Google Deployment Manager][1], [Terraform][2], and others) are:

- Docker-first philosophy: resource types (eg. VMs, IP-addresses, disks,
etc) are written as Docker images, allowing them to be reused in any
deployment, on any platform.

- Highly extensible: since resource implementations are merely Docker
images - you can create new resource types by creating your own Docker
images, using any technology you want. Want to create a new resource
that represents a GitHub repository using Ruby? Done. Just implement a
new Docker image and write your source code in Ruby inside the image,
then use that resource in any Deployster manifest. The Docker image name
& tag represent the resource type.

- Stateless: in contrast to similar tools, Deployster will never store
your topology state (locally or remotely) which enables your to also
work on your infrastructure & deployments manually or in other tools,
side-by-side with Deployster. While we are aware that this might incurr
a performance penalty at times (for state discovery) we believe this is
preferrably to a _wrong state discovery_.

- Reproducible: deployments are meant to be idempotent, such that
running the same deployment multiple times should yield the same result
as running it just once, assuming that nothing else modified the state.

## Credits

Deployster was written by the team @ Infolinks as a means to improve
our deployment process. We plan to gradually open source more & more
components of that pipeline in the coming months.
