from external_services import ExternalServices
from k8s import K8sResource


class K8sIngress(K8sResource):

    def __init__(self, data: dict, svc: ExternalServices = ExternalServices()) -> None:
        super().__init__(data=data, svc=svc)

    def is_available(self, state: dict) -> bool:
        # TODO: consider waiting for kube-lego to generate the TLS certificate from LetsEncrypt (if it's installed)
        if 'status' not in state:
            return False

        status = state['status']
        if 'loadBalancer' not in status:
            return False

        load_balancer_status = status['loadBalancer']
        if 'ingress' not in load_balancer_status:
            return False

        if [ing for ing in load_balancer_status['ingress'] if 'hostname' in ing or 'ip' in ing]:
            return True
        else:
            return False
