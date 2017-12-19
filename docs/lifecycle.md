# Deployment lifecycle & resource protocol

Deployster progress through a set of well defined phases during
deployment. Each phase is responsible for a specific task, and this
document will outline them here:

### Initialization

During this phase Deployster will query all resources (in no particular
order) for initialization information. It will do that by running each
resource's Docker image with its default entrypoint and no arguments.
This is called the `init` action, and Deployster will send the action,
via `stdin`, some of the information it knows about the resource:

- **the resource's name**, as it is specified in the manifest
- **the resource's type** (essentially the name of the Docker image &
tag) This enables you to use the same Docker image to implement multiple
resource types, and distinguish between which resource is being handled
for the current invocation.
- **the Deployster version** (enables resource types to reject
unsupported Deployster versions for being too old or too new)
- **the verbosity flag**, allows the user to request more information
to be printed out (for debugging or just for logging)

All of this is sent via `stdin` as JSON, in the following format:

```json
{
  "name": "www_vm",
  "type": "acme/deployster-aws-vm",
  "version": "18.0.0",
  "verbose": false
}
```

The resource response must be sent back also as JSON on `stdout` and can
contain the following information (some is optional):

- **configuration schema** for validating the resource configuration for
this resource in the deployment manifest. The schema is written as
[JSON schema][1] and if provided, will enable Deployster to halt
execution if the user-provided configuration for the resource fails to
validate successfully.
- **plugs** that the resource supports or even requires. This enables
resource type to specify which plugs are required, which plugs are
optional, and for each plug whether the resource wants write access or
just to read from.
- **the state action (required)**: this is where the resource type specifies how
to discover the actual resource's state. Essentially, it provides
information on how to run the Docker image (can be another image) in
order to request state discovery.

Here's an example of a resource `init` action response on `stdout`:

```json
{
  "plugs": {
    "gcp_service_account_file": {
      "container_path": "/internal/path/to/mount/the/plug/in/container",
      "optional": false,
      "writable": false
    }
  },
  "config_schema": {
    "type": "object",
    "additionalProperties": true
  },
  "state_action": {
    "args": ["state"]
  }
}
```

The above JSON when returned from a resource's `init` action means that
the resource requests a plug named `gcp_service_account_file`, and that
it is a required plug (so if the user did not define such a plug, the
deployment will halt), but that the resource does not need to write into
it (so the plug will be mounted to the resource's Docker image in
read-only mode). You can request any number of plugs of course.

The next thing we see is that the resource defines a configuration
schema. Please read the JSON schema specification or tutorials on the
web for more information on writing JSON schemas. The simple schema
above simply means that the configuration must be an object (the only
mode supported by Deployster) and that any property may be put on it.

Next we see the `state_action` property which says that in order to
discover the represented resource's state, Deployster should invoke the
same Docker image, but this time with an extra argument "state" (the
`init` action had no arguments, remember?)

Feel free to inspect the [`init` action JSON schema][2] for a detailed
representation.

## Resource sorting

We haven't mentioned this yet, but you can declare dependencies between
resources. Declaring that a resource `www_vm` _depends_ on the resource
`my_data_disk`, means that Deployster will first resolve & apply the
`my_data_disk` resource, and only if that succeeds, it will then resolve
and apply the `www_vm` resource.

Here's a simple example showing how to declare resource dependencies:

```YAML
resources:
  
  my_data_disk:
    type: acme/deployster-gcp-disk
    config:
      name: www_data_disk
      size: '200gb'

  www_vm:
    type: acme/deployster-gcp-vm
    dependencies:    
      disk: my_data_disk
    config:
      name: www_vm
      machine-type: n1-standard-4
```

When Deployster will run, it will always first resolve & apply the
`my_data_disk` resource, and then `www_vm`.

## Execution

Once all resources are initialized & sorted, Deployster will iterate the
resources (in a dependency-aware sorting order) to _resolve_ and
_apply_ each one.

#### Resolving resources

Resolving a resource means discovering its current state in the target
topology. Once we know its state we can then find out what's required
to bring it to the _desired_ state - which is essentially how you
described the resource in the deployment manifest.

Before, however, we attempt to discover the resource's state, Deployster will first post-process the resource's configuration clause and resolve any expressions you may have used in it. The expressions are expected to be Jinja2 expressions, and they have access to the following context:

- any global context variables (defined via `--var` and `--var-file` command line arguments, as well as auto-variables files)
- resource dependencies: for each dependency, a key in the expression context is defined, who value is an object containing:
  - the `name` key, containing the dependency resource's name (not necessarily the name given in the dependency map)
  - the `type` key, containing the dependency resource's type
  - the `state` key, containing the resolved state of the dependency. Since we know that the resource's dependencies have been resolved prior to resolving this resource, we know that they have been resolved & applied and we have their current state (after deploying them). This updated state is available here.

Once all expressions under the `config` clause of the resource have been resolved, Deployster will then invoke the resource's `state action`, as provided in the response of the `init action` (see _Resource initialization_ above). The state action is provided with extended information, also sent via `stdin`, which contains:

- all information originally sent to the `init action`
- `config` will contain the resource configuration clause, with all expressions resolved.

Lets improve the example manifest above by adding an expression to the
`www_vm` resource's `config` clause:

```YAML
resources:
  
  my_data_disk:
    type: acme/deployster-gcp-disk
    config:
      name: www_data_disk
      size: '200gb'

  www_vm:
    type: acme/deployster-gcp-vm
    dependencies:    
      disk: my_data_disk
    config:
      name: www_vm
      zone: '{{ www_data_disk.state.zone }}'
      machine-type: n1-standard-4
```

You can see that the manifest specifies that the `zone` property of the `www_vm` resource should get its value from the expression `www_data_disk.state.zone`, which means:

_"get the property `zone` from the `state` of the `www_data_disk` resource"_.

So how would the input to the `state` action of `www_vm` resource look like? Lets assume that the `www_data_disk` resource exposed a `zone` property in its state with the value of `europe-west1-b`, the JSON sent to the `www_vm` resource on `stdin` would look like this:

```JSON
{
  "name": "www_vm",
  "type": "acme/deployster-aws-vm",
  "version": "18.0.0",
  "verbose": false,
  "config": {
    "name": "www_vm",
    "zone": "europe-west1-b",
    "machine-type": "n1-standard-4"
  }
}
```

Deployster runs the resource's state action (eg. `docker run ...`) and sends this JSON to that process (if you recall, the state action's Docker image, entrypoint & arguments are provided by the resource's `init` action). The `state` action now has to respond back (in its `stdout`) with JSON that provides the resource's current state, and the list of actions required to bring that resource to the desired state (which is provided to the action via `stdin` in the `config` property).

The response must match one of two possibilities:

1. Provide a `status` property equaling `VALID`, and another property called `state` with the current updated state of the resource. Returning such a response in essence means _"this resource matches the provided configuration in full, and no action is necessary".
2. Provide a `status` property with the value of `STALE`, an optional property named `staleState` with the _current_ state of the resource (can be omitted if the resource simply does not exist) and another mandatory property named `actions` which is an array of JSON objects that provide the list of actions that need to be executed to bring the resource on par with the resource configuration (ie. _desired state_).

An example of a `VALID` resource would look as such:

```JSON
{
  "status": "VALID",
  "state": {
    "name": "www_vm",
    "zone": "europe-west1-b",
    "machine-type": "n1-standard-4"
  }
}
```

Such a response essentially signals to Deployster that:

- This resource exists.
- It matches the provided `config` property completely (aka. _desired state_).
- No action is necessary.

The `actions` property is **forbidden** in this scenario (ie. when `status` equals `VALID`).

Alternatively, if the resource _does not_ match the provided configuration, the response should be something similar to this:

```JSON
{
  "status": "STALE",
  "actions": [
    { 
      "name": "create-vm", 
      "description": "Create VM", 
      "entrypoint": "/acme/scripts/create-vm.sh"
    },
    { 
      "name": "notify-slack", 
      "description": "Signal new VM on slack",
      "image": "acme/slack-notifier",
      "entrypoint": "/acme/scripts/slack.sh", 
      "args": ["--room=acme_deployments_channel"]
    }
  ]
}
```

Such a response essentially signals to Deployster that:

- This resource _does not_ exist.
- Two actions are required to bring it to the _desired state_. You can see that the action definitions look very similar to how the `state` action was provided as part of the `init` action's response; in Deployster "lingo", an action is simply a spec for how to invoke Docker - an (optional) image name (defaults to the same image of the resource), the (optional) image entrypoint (defaults to the image's default entrypoint), and (optional) image extra arguments!

What if the resource _did_ exist, but is out of date for some reason - lets say its _machine-type_ is `n1-standard-1` instead of `n1-standard-4` because someone changed it manually few days ago. The response would look as such:

```JSON
{
  "status": "STALE",
  "staleState": {
    "name": "www_vm",
    "zone": "europe-west1-b",
    "machine-type": "n1-standard-1"
  },
  "actions": [
    { 
      "name": "update-vm-machine-type",
      "description": "Update VM machine type", 
      "args": ["--machine-type=n1-standard-4"]
    }
  ]
}
```

#### Applying resources

The process of _applying_ resources means _applying_ the set of actions provided by each resource's `state` action. So by saying _applying an action_ we simply mean _executing an action_.

Continuing the example from the _Resolving resources_ section above, assuming we need to execute one action (the `update-vm-machine-type` action) - all that Deployster needs to do then, is execute Docker image of the resource type (since that action did not provide an `image` property in its JSON) with the default entrypoint (since the action also did not provide an `entrypoint` property) and send a single argument: `--machine-type=n1-standard-4`

If all the actions for a resource succeed, Deployster then re-queries that resource's `state` action, expecting it to now return the `VALID` status. Any action that fails (by returning a non-zero exit code) or if the subsequent invocation of the state action _does not_ return a `VALID` status, Deployster halts the execution with the appropriate error message.


[1]: http://json-schema.org    "JSON Schema"
[2]: https://github.com/infolinks/deployster/blob/master/src/schema/action-init-result.schema "init action JSON schema"
