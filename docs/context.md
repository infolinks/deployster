# Deployment context

It's often the case that elements in your deployment manifest need to be
dynamic, based on things such as the target environment. Deployster
allows you to avoid saving those elements inside the manifest by
enabling you to provide them through the _context_.

The context is a collection of variables (name & value) that is provided
externally from the deployment manifest, through either the Deployster
command line or from a set of one or more variable files (or both).

Once the context has been initialized, it is used by Deployster for post
processing the manifest. Post processing is performed using [Jinja2][3].
