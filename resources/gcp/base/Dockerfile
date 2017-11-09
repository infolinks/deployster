FROM infolinks/cloud-sdk:178.0.0-alpine
MAINTAINER Arik Kfir <arik@infolinks.com>
RUN apk --no-cache --update add jq tree bash python3 py3-pip && \
    pip3 install google-api-python-client ansicolors
ENV PYTHONPATH "/deployster/lib:$PYTHONPATH"
COPY gcp/src/ /deployster/lib/
