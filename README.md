# deployster

[![Build status](https://badge.buildkite.com/55e25a8e5c77c2393c8a73d78a343d623ab77bca48875ded10.svg)](https://buildkite.com/infolinks/deployster)
[![Coverage Status](https://coveralls.io/repos/github/infolinks/deployster/badge.svg)](https://coveralls.io/github/infolinks/deployster)

Deployster is an extensible resource-centric deployment tool. It allows
developers to declare their _desired_ state of the deployment plane &
toplogy, and then attempts to migrate from the _current_ state into the
_desired_ state.

## Documentation

<aside class="warning">
The documentation is still in its early phases. Some of the information
may be a bit out of date or inaccurate. We are sorry for this temporary
state and hope to finish documenting Deployster soon!
</aside>

Deployster documentation can be found at
[http://www.deployster.online](http://www.deployster.online).

## Credits

Deployster was written by the team @ Infolinks as a means to improve
our deployment process. We plan to gradually open source more & more
components of that pipeline in the coming months.

# Outdated

Everything beyond this point _might be_ outdated and is pending review.

### Manifest

The deployment manifest is a YAML document that lists a set of _plugs_
and _resources_. Together, they formulate the desired state of your
deployment topology.

An example manifest looks like this:

```YAML
# available plugs:
plugs:
  some_plug:
    path: /some/path                    # required
    read_only: true                     # defaults to false
    resource_types:                     # allowed resource types list (regex)
        - ^some/image-repository.*
    resource_names:                     # allowed resource names list (regex)
        - ^my_prefix.*$

# resources to deploy:
resources:

  # deployster will check if project exists, and create it if not
  project:
    type: infolinks/deployster-gcp-project
    config:
      project_id: acme-prod
      organization_id: 123
```

## Running

Deployster is distributed as a Docker image available for running on
your machine or servers. Here's an example command-line usage:

```bash
deployster.sh ./my-manifest.yaml \
              --var my_var="some-value" \
              --var another="some-value" \
              --var-file ./my-variables-file.yaml \
              --var my_overriding_variable="overrides 'my_overriding_variable' in the variables file"
              ...
```

This invocation registers two variables in the context (`my_var` and
`another`), as well as any variables defined in the `my-variables-file.yaml`
file, and finally another variable (`my_overriding_variable`). If the
`my-variables-file.yaml` also defines `my_overriding_variable`, the
one on the command-line takes precedence **because it was provided
_after_ the `--var-file` argument.

You can also invoke the Deployster Docker image manually, like this:

```bash
docker run -it \                                            # enable interactivity
           -v $(pwd):/deployster/workspace \                # mount your workspace
           -v /var/run/docker.sock:/var/run/docker.sock \   # enable Docker-in-Docker
           infolinks/deployster:latest \                    # the Deployster version to run
           ./my-manifest.yaml \
           --var my_var="some-value" \
           --var another="some-value" \
           --var-file ./my-variables-file.yaml \
           --var my_overriding_variable="overrides 'my_overriding_variable' in the variables file"
 ```

#### Providing context variables

You can provide ad-hoc variables to the context by using the `--var`
flag in the command line, like this:

    --var my_var=some-value

The `my_var` variable will be available in the context for
post-processing the manifest. For example, here's a manifest snippet
that uses the variable:

```YAML
plugs:
    ...

resources:
    my-vm:
        description: {{ my_var }}
```

For a more persistent method of storing your variables (instead of
providing them on the command line) you can store them in YAML variable
files, like this:

```YAML
my_var: some-value
some_person:
    name: Joe
    age: 42
```

Provide it on invocation, like so:

    --var-file /path/my-variables.yaml

You can now use `{{ my_var }}` in your manifest, as well as
`{{ some_person.name }}` or `{{ some_person.age }}`.

[1]: https://cloud.google.com/deployment-manager/docs/configuration/supported-resource-types    "Google Deployment Manager"
[2]: https://www.terraform.io/docs/providers/external/data_source.html                          "Terraform"
[3]: http://jinja.pocoo.org/                                                                    "Jinja2"
