from dresources import DResource


# noinspection PyAbstractClass
class GcpResource(DResource):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.add_plug(name='gcp-service-account',
                      container_path='/deployster/service-account.json',
                      optional=False, writable=False)
