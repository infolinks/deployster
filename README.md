# deployster

[![Build status](https://badge.buildkite.com/55e25a8e5c77c2393c8a73d78a343d623ab77bca48875ded10.svg)](https://buildkite.com/infolinks/deployster)

Deployster is an extensible resource-centric deployment tool. It allows
developers to declare their _desired_ state of the deployment plane &
toplogy, and then attempts to migrate from the _current_ state into the
_desired_ state.

The difference between Deployster and other similar tools such as
[Google Deployment Manager][1], [Terraform][2] and others is its extensibility:

- Extensible: new resource types can be easily added
- Docker-first philosophy: resources are written as Docker images, which
allows resource implementors to use any tool they deem appropriate
- Stateless: in contrast to similar tools, Deployster will never store
your topology state (locally or remotely) which enables your to also
work on your infrastructure & deployments manually or in other tools,
side-by-side with Deployster.
- Reproducible: deployments are meant to be idempotent, such that
running the same deployment multiple times should yield the same result
as running it just once, assuming that nothing else modified the state.
- Smart: Deployster allows (and sometimes requires) inter-resource
dependencies, which enable Deployster to roll out actions in the
appropriate order.
- Safe: everyone makes mistakes, and nobody likes dealing with them at
midnight :)
    - Deployster attempts to help by being fully transparent about
    what it is about to do and what it actually does.
    - Will support _Rollbacks_ which will enable you to more easily
    recover from accidental roll-outs.

## Examples

Examples are available under the `examples` directory - please have a
look!

## Architecture

Deployster mechanics is built around three main components:

- Resource Types: each resource type is essentially a Docker image that
implements a simple contract that allows receiving configuration,
querying the resource state, and performing an action.

- Manifest: a YAML or JSON document (TBD) written by the
deployer or developer, that describes _what_ the final state should be.
It's Deployster's job to use this manifest to _discover_ the current
state, and then plan the set of actions that will migrate it to the
_desired_ state as described in the manifest.

- Context: a separate set of variables (inferred from command-line
variables and/or YAML or JSON documents) augmenting the manifest with
dynamic values, allowing you to use the same manifest in different
environments or scenarios. For example, the manifest may specify that
a Kubernetes cluster is to be deployed, but the number of nodes would
probably be different between production & QA - this is a value you
would store in the context instead of the manifest.

### Manifest

The deployment manifest is a YAML document that lists a set of _plugs_
and _resources_. Together, they formulate the desired state of your
deployment topology.

An example manifest looks like this:

```YAML
plugs:
  some_plug:
    path: /some/path

resources:
  project:
    type: infolinks/deployster/gcp/project:latest
    config:
      project_id: acme-prod
      organization_id: 123
```

### Context

It's often the case that elements in your deployment manifest need to be
dynamic, based on things such as the target environment. Deployster
allows you to avoid saving those elements inside the manifest by
enabling you to provide them through the _context_.

The context is a collection of variables (name & value) that is provided
externally from the deployment manifest, through either the Deployster
command line or from a set of one or more variable files (or both).

Once the context has been initialized, it is used by Deployster for post
processing the manifest. Post processing is performed using [Jinja2][3].

### Plugs

Plugs are shared persistent directories by which resources can inter-
communicate between themselves as well as a mechanism through which you
can provide required configuration files to resources, such as
Docker authentication configuration.

You define available plugs in your manifest. For each plug, you define
a local directory, mount mode (read-only or read-write), and optionally
restrict which resources are allowed to receive the plug.

Once plugs are defined in the context, resources can request some of the
plugs for execution (see below on resource execution phases) and the
relevant plugs will be mounted to the resources Docker images.

### Resources

Resources in Deployster are Docker images that comply to a simple
protocol. The actual Docker image can be implemented using any language,
eg. Bash, Python, Ruby, Java, or any other language that's able to read
and write to `stdin` & `stdout`/`stderr` (ie. any technology).

The protocol between Resource images and Deployster is composed of the
following phases:

#### Resource initialization

On startup, Deployster will run the image using its default entry
point, and will provide the following structure under `stdin`:

```json
{
    "name": "<resource-name>"
}
```

This isn't much to work with, of course - but the intention of this
invocation is mainly to allow the resource to provide back to Deployster
information about the resource; therefor, Deployster will expect the
following structure back:

```javascript
{
    // The resource type's label, eg. "Google Cloud VM"
    "label": "<resource-type-label>",

    // Set of required "plugs" for this resource (see below for more info)
    "required_plugs": {
        "<plug-name>": "<path-to-mount-plug-on-future-invocations>",
        ...
    },

    // Set of required resource dependencies that this resource requires
    // the user to define and pass as dependencies to this resource
    "required_resources": {
        "<dependency-alias>": "<expected-resource-type>",
        ...
    },


    // The JSON schema to validate the resource's configuration in
    // the manifest. The configuration that the user provides for
    // the resource in the manifest will be validated against this
    // schema by Deployster.
    //
    // JSON schema home: http://json-schema.org/
    "config_schema": {
        ...
    },

    // The action to invoke to fetch the updated state of this resource.
    // This action should use any APIs or any other means to check
    // whether the resource exists, out-of-date, or fully deployed and
    // report that status back, along with any required actions that
    // are needed in order to make the resource fully deployed.
    "state_action": {
        "image": "<docker-image-of-the-action>",            // optional: can be used to specify a different image
        "entrypoint": "<action-entrypoint-in-the-image>",   // recommended: the entrypoint that will execute the action
        "args": [ ... ]                                     // optional: extra argument strings to the entrypoint
    }
}
```

#### Resource resolving

Once all resources have been initialized (see above), Deployster will
then ask each resource for it's most up-to-date state. Each resource
can reply that it does not exist at all, exists but not fully
confirming to the desired state (eg. one of the properties' actual value
does not equal to its desired value), or exists and fully conformant.

The way this happens is by Deployster invoking the _state action_ that
the resource provided during the _initialization_ phase. This action,
when executed, is provided the following JSON structure on its `stdin`:

```javascript
{
    // The name of the resource in the deployment manifest
    "name": "<resource-name>",

    // The type of the resource; this is the Docker image of the resource
    "type": "<resource-type>",

    // The resource configuration as given in the manifest
    "config": {
        ...
    },

    // References to required resource dependencies.
    "dependencies": {
        "<dependency-resource-alias>": {

            // The type of the dependency resource
            "type": "<dependency-resource-type>",

            // The dependency resource configuration as given in the manifest
            "config": {
                ...
            },

            // Recursively provides dependencies-of-dependencies...
            "dependencies": {
                ...
            }
        },
        ...
    }
}
```

Using this information - mainly the manifest configuration for this
resource, and the resource's dependencies - the resource can use
whatever means it deems necessary to discover the current state of the
resource. The state action is expected to output the following JSON
on its `stdout`:

```javascript
{
    "status": "<resource-status>", // must be "MISSING", "STALE", or "VALID"

    // If the resource is "MISSING" or "STALE", a list of actions MUST be provided:
    "actions": [
        {
            "name": "<action-name>",    // eg. "create-aws-address"
            "description": "...",       // eg. "Create AWS address 'your-name'"
            "image": "...",             // optional, can be used to switch to another image
            "entrypoint": "...",        // the action's entrypoint to execute
            "args": [ ... ],            // optional arguments to the entrypoint
        }
    ],

    // Otherwise, if resource is "VALID", its current statue MUST be provided
    // using the "properties" property:
    "properties": {
        ...
    }
}
```

Therefor, if the resource determines that the resource does not exist,
it should return a status of `MISSING`, along with a list of _actions_
that will propertly create the resource in the desired state.

Alternatively, if the state action determines that the resource does
exist, but its state is not as it should be (eg. a cluster resource's
node count is different that desired for some reason), it should return
a status of `STALE`, along with a list of actions that will modify the
resource to be in the exact desired state (eg. modify the cluster to
contain the desired number of nodes).

If the resource exists and is in the desired state already, the state
action should return a status of `VALID`, along with an up-to-date
representation of the resource state as a properties map, under the
`properties` proeprty.

**TODO:** document how a resource's state is automatically inferred to
be `MISSING` if any of its resources is `MISSING`, and its state action
is only executed later on, after its dependencies have been updated.

#### Execution order

When the state for all resources has been fetched by invoking their
state actions, Deployster will sort the collected actions from all
`MISSING` and `STALE` resources, by ensuring that each resource's
actions are executed _after_ all actions of all its dependencies are
executed.

#### Action execution

For each resource that's either `MISSING` or `STALE`, the list of
actions that are needed to bring it to the `VALID` state will be
executed. Each such action, when executed, is provided with the same
JSON structure as provided to the state action, with one additional
property, provided for each dependency resource: the `properties`
property, under each dependency. It will contain the resource's state
as provided by that resource's state action under its own `properties`
property.

So each resource's actions will receive the fully up-to-date state
of all its dependencies when it is executed.

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

#### Planning

To test your manifest without actually running it, you can add the
`--plan` flag, which will instruct Deployster to print out the
deployment plan and exit immediately (don't worry - even if you don't
add this flag, Deployster will compute ask you for confirmation before
actually executing the deployment, unless you add `--yes` to the command
line).

## Available resources

TBD.

## ROADMAP

- [ ] Support creating a Plan from a previously-saved plan file (incl. comparing updated state to saved state)
- [ ] Support live-streaming of resource action stdout to console (excluding init & state actions)
- [ ] Support marking resources as deleted; useful to have Deployster ensure a certain resource DOES NOT exist
- [ ] Support patterns for plug permissions
- [ ] Resource dependency mechanism improvements
        - [ ] Optional resource dependencies
        - [ ] Dependency lists (give me a list of dependencies of type X)
- [ ] Support manifest fragments (ie. inclusion of manifests from other manifests)
- [ ] Support auto-included variable files (eg. `context.auto.<*>.yaml`)
- [ ] Support configurable action timeouts (per action preferably)
        - [x] Already supported by Kubernetes resources
- [ ] Support rollback actions
- [ ] Potential performance improvements:
        - Parallel execution paths
- [ ] Change all GCP resources to accept a service account JSON file _instead_ of a `gcloud` plug
        - Avoid having a user's `gcloud` directory having `root`-owned files
- [ ] GKE cluster resource should require a `kube` plug into which it will write authenticated `kubectl` configuration
        - This plug should then be provided to all other Kubernetes resources
        - This will enable making Kubernetes resources GKE-agnostic, and work on any Kubernetes cluster
        - Will boost performance a bit by avoiding re-authentication for each resource
- [x] Unify cluster roles and namespace roles (and their bindings)
- [ ] Log operation timing (per resource, per phase(init/discovery/execution), and total)
- [ ] Setup a test which performs a full deployment to a throwaway project, sends test requests, and tears down.
- [ ] Support loading variables from `~/.deployster.auto.<*>.yaml`
- [ ] Create "Helm Chart" resource

[1]: https://cloud.google.com/deployment-manager/docs/configuration/supported-resource-types    "Google Deployment Manager"
[2]: https://www.terraform.io/docs/providers/external/data_source.html                          "Terraform"
[3]: http://jinja.pocoo.org/                                                                    "Jinja2"
