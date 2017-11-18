FROM infolinks/deployster-gcp-base:local
MAINTAINER Arik Kfir <arik@infolinks.com>
COPY gcp/container/cluster/*.py /deployster/
RUN chmod +x /deployster/*.py
ENTRYPOINT ["/deployster/cluster-init.py"]
