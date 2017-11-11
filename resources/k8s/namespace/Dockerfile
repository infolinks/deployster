FROM gcr.io/infolinks-gcr/deployster-k8s-base:local
MAINTAINER Arik Kfir <arik@infolinks.com>
COPY k8s/namespace/*.py /deployster/
RUN chmod +x /deployster/*.py
ENTRYPOINT ["/deployster/namespace-init.py"]
