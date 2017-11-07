# Resources

True to our Docker-first philosophy, Resource Types are Docker images.
Each resource type is simply a unique Docker image which is executed and
expected to implement a certain contract, which allows Deployster to
communicate with it.

## Workflow



- `state.sh`:
Every resource image must support this entrypoint.
    - Deployster passes
