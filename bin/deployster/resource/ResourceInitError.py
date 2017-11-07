class ResourceInitError(Exception):
    def __init__(self, message, resource, *args):
        super().__init__(*args)
        self._message = message
        self._resource = resource

    @property
    def message(self):
        return self._message

    @property
    def resource(self):
        return self._resource
