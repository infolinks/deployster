from k8s import K8sResource
from k8s_services import K8sServices


class K8sService(K8sResource):

    def __init__(self, data: dict, k8s_services: K8sServices = K8sServices()) -> None:
        super().__init__(data, k8s_services)

    def is_available(self, state: dict) -> bool:
        manifest = self.info.config['manifest']
        if 'spec' not in manifest:
            return True

        spec = manifest['spec']
        if 'type' not in spec:
            return True

        service_type: str = spec['type']
        if service_type != 'LoadBalancer':
            return True

        if 'status' not in state:
            return False

        status = state['status']
        if 'loadBalancer' not in status:
            return False

        load_balancer_status = status['loadBalancer']
        if 'ingress' not in load_balancer_status:
            return False

        ingresses_status = load_balancer_status['ingress']
        if [ing for ing in ingresses_status if 'hostname' in ing or 'ip' in ing]:
            return True
        else:
            return False
