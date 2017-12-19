# Resource Protocol

As mentioned in the [overview](./overview) page, each resource has a
type, and that type is simply a Docker image. Deployster will run the
image multiple times during the deployment lifecycle

Resources in Deployster are Docker images that comply to a simple
protocol. The actual Docker image can be implemented using any language,
eg. Bash, Python, Ruby, Java, or any other language that's able to read
and write to `stdin` & `stdout`/`stderr` (ie. any technology).

The protocol between Resource images and Deployster is composed of the
following phases:

## Resource initialization

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

## Resource resolving

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

## Execution order

When the state for all resources has been fetched by invoking their
state actions, Deployster will sort the collected actions from all
`MISSING` and `STALE` resources, by ensuring that each resource's
actions are executed _after_ all actions of all its dependencies are
executed.

## Action execution

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
