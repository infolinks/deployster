# Introduction

[![Build status](https://badge.buildkite.com/55e25a8e5c77c2393c8a73d78a343d623ab77bca48875ded10.svg)](https://buildkite.com/infolinks/deployster)
[![Coverage Status](https://coveralls.io/repos/github/infolinks/deployster/badge.svg)](https://coveralls.io/github/infolinks/deployster)

Deployster is an extensible resource-centric deployment tool that works by:

- Enabling deployers (eg. _You!_) declare the _desired_ state of the deployment topology
- It then discovers the topology's _current_ state
- It then attempts to migrate it from the _current_ state to the _desired_ state.

The main differences between Deployster and other, similar, tools (such as [Google Deployment Manager][1], [Terraform][2], and others) are:

- **Docker-first philosophy**: resource types (eg. VMs, IP-addresses, disks,
etc) are written as Docker images, allowing them to be reused in any deployment, on any platform.

- **Highly extensible**: since resource implementations are merely Docker images - you can create new resource types by creating your own Docker images, using any technology you want. Want to create a new resource that represents a GitHub repository using Ruby? Done. Just implement a new Docker image and write your source code in Ruby inside the image, then use that resource in any Deployster manifest. The Docker image name & tag represent the resource type.

- **Stateless**: in contrast to similar tools, Deployster will never store your topology state (locally or remotely) which enables your to also work on your infrastructure & deployments manually or in other tools, side-by-side with Deployster. While we are aware that this might incurr a performance penalty at times (for state discovery) we believe this is preferrable to a _wrong state discovery_.

- **Reproducible**: deployments are meant to be idempotent, such that running the same deployment multiple times should yield the same result as running it just once, assuming that nothing else modified the state.

### Getting started & documentation

The [quick start](http://www.deployster.online/quickstart) page will get you up & running in 10 minutes. For a more in-depth overview of Deployster, head over to the [overview](http://www.deployster.online/overview) page to learn more about the core concepts in Deployster.

### And for the lazy...

Deployster is distributed as a Docker image available for running on your machine or servers. Since the image requires a certain set of Docker flags, a simple `bash` script is provided which makes running Deployster a breeze. Here's how:

```bash
curl -sSL -O "https://raw.githubusercontent.com/infolinks/deployster/master/deployster.sh"
./deployster.sh --var my_var="some-value" \
                --var another="some-value" \
                --var-file ./my-variables-file.yaml \
                ./manifest1.yaml ./manifest2.yaml
```

Here's the full run-down of command-line flags available:

```
[arik@arik ~]$ curl -sSL -O "https://raw.githubusercontent.com/infolinks/deployster/master/deployster.sh" && chmod +x ./deployster.sh
[arik@arik ~]$ ./deployster.sh --help

✔ Deployster v18.0.1

      😄 Deploy with pleasure!
      
usage: deployster.py [-h] [-c {NO,ONCE,RESOURCE,ACTION}] [--var NAME=VALUE]
                     [--var-file FILE] [-p] [-v]
                     manifests [manifests ...]

Deployment automation tool, v18.0.1.

positional arguments:
  manifests             the deployment manifest to execute.

optional arguments:
  -h, --help            show this help message and exit
  -c {NO,ONCE,RESOURCE,ACTION}, --confirm {NO,ONCE,RESOURCE,ACTION}
                        confirmation mode
  --var NAME=VALUE      makes the given variable available to the deployment
                        manifest
  --var-file FILE       makes the variables in the given file available to the
                        deployment manifest
  -v, --verbose         increase verbosity

Written by Infolinks @ https://github.com/infolinks/deployster
```

<aside class="warning">
The documentation is still in its early phases. Some of the information may be a bit out of date or inaccurate. We are sorry for this temporary state and hope to finish documenting Deployster soon!
</aside>

### Credits

Deployster was written by the team @ Infolinks as a means to improve our deployment process. We plan to gradually open source more & more components of that pipeline in the coming months.

[1]: https://cloud.google.com/deployment-manager/docs/configuration/supported-resource-types    "Google Deployment Manager"
[2]: https://www.terraform.io/docs/providers/external/data_source.html                          "Terraform"
[3]: http://jinja.pocoo.org/                                                                    "Jinja2"
