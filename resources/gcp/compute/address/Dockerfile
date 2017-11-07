FROM gcr.io/infolinks-gcr/deployster-gcp-base:local
MAINTAINER Arik Kfir <arik@infolinks.com>
COPY gcp/compute/address/*.py /deployster/
RUN chmod +x /deployster/*.py
ENTRYPOINT ["/deployster/address-init.py"]
