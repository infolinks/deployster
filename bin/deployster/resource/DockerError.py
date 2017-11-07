class DockerError(Exception):
    def __init__(self, message, process, *args):
        super().__init__(*args)
        self._message = message
        self._process = process

    @property
    def message(self):
        return self._message

    @property
    def process(self):
        return self._process
