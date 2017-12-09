FROM alpine:3.6
MAINTAINER Arik Kfir <arik@infolinks.com>

# setup python & pip dependencies
COPY requirements.txt /deployster/
RUN apk --no-cache --update add bash docker jq python3 py3-pip && \
    pip3 --quiet --disable-pip-version-check --no-cache-dir install -r /deployster/requirements.txt

# setup environment & version
ENV PYTHONPATH="/deployster/lib"
ENV PYTHONUNBUFFERED="1"
ARG VERSION="0.0.0"
RUN echo "${VERSION}" > /deployster/VERSION
COPY src /deployster/lib
RUN chmod a+x /deployster/lib/deployster.py
ENTRYPOINT ["/deployster/lib/deployster.py"]
