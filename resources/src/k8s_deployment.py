from k8s import K8sResource
from k8s_services import K8sServices


class K8sDeployment(K8sResource):

    def __init__(self, data: dict, k8s_services: K8sServices = K8sServices()) -> None:
        super().__init__(data, k8s_services)

    def is_available(self, state: dict) -> bool:
        if 'status' not in state:
            return False

        status = state['status']
        if 'unavailableReplicas' not in status:
            return True

        unavailable_replicas = status['unavailableReplicas']
        return unavailable_replicas == 0
