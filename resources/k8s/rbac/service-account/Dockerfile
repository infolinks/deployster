FROM infolinks/deployster/k8s/base:local
MAINTAINER Arik Kfir <arik@infolinks.com>
COPY k8s/rbac/service-account/*.py /deployster/
RUN chmod +x /deployster/*.py
ENTRYPOINT ["/deployster/service-account-init.py"]
