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

```JSON
{
  "name": "my_vm",
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

## Execution

Once all resources are initialized, we know each resource'
[1]: http://json-schema.org    "JSON Schema"
[2]: https://github.com/infolinks/deployster/blob/master/src/schema/action-init-result.schema "init action JSON schema"
