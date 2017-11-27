# Resource plugs

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
