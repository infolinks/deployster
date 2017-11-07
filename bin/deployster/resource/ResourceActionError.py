class ResourceActionError(Exception):
    def __init__(self, message, *args):
        super().__init__(*args)
        self._message = message

    @property
    def message(self):
        return self._message
