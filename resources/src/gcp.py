from dresources import DResource

# noinspection PyAbstractClass
from gcp_services import GcpServices


# noinspection PyAbstractClass
class GcpResource(DResource):

    def __init__(self, data: dict, gcp_services: GcpServices) -> None:
        super().__init__(data)
        self._gcp: GcpServices = gcp_services
        self.add_plug(name='gcp-service-account',
                      container_path='/deployster/service-account.json',
                      optional=False, writable=False)

    @property
    def gcp(self) -> GcpServices:
        return self._gcp
