from external_services import ExternalServices
from k8s import K8sResource


class K8sService(K8sResource):

    def __init__(self, data: dict, svc: ExternalServices = ExternalServices()) -> None:
        super().__init__(data=data, svc=svc)

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
