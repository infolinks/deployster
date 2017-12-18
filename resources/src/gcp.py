from dresources import DResource

# noinspection PyAbstractClass
from external_services import ExternalServices


# noinspection PyAbstractClass
class GcpResource(DResource):

    def __init__(self, data: dict, svc: ExternalServices) -> None:
        super().__init__(data=data, svc=svc)
        self.add_plug(name='gcp-service-account',
                      container_path='/deployster/service-account.json',
                      optional=False, writable=False)
