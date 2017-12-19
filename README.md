# deployster

[![Build status](https://badge.buildkite.com/55e25a8e5c77c2393c8a73d78a343d623ab77bca48875ded10.svg)](https://buildkite.com/infolinks/deployster)
[![Coverage Status](https://coveralls.io/repos/github/infolinks/deployster/badge.svg)](https://coveralls.io/github/infolinks/deployster)

Deployster is an extensible resource-centric deployment tool. It allows developers to declare their _desired_ state of the deployment plane & toplogy, and then attempts to migrate from the _current_ state into the _desired_ state.

## Documentation

<aside class="warning">
The documentation is still in its early phases. Some of the information may be a bit out of date or inaccurate. We are sorry for this temporary state and hope to finish documenting Deployster soon!
</aside>

Deployster documentation can be found at [http://www.deployster.online](http://www.deployster.online).

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

## Credits

Deployster was written by the team @ Infolinks as a means to improve our deployment process. We plan to gradually open source more & more components of that pipeline in the coming months.

[1]: https://cloud.google.com/deployment-manager/docs/configuration/supported-resource-types    "Google Deployment Manager"
[2]: https://www.terraform.io/docs/providers/external/data_source.html                          "Terraform"
[3]: http://jinja.pocoo.org/                                                                    "Jinja2"
