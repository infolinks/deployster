FROM alpine:3.6
MAINTAINER Arik Kfir <arik@infolinks.com>
RUN apk --no-cache --update add bash docker jq python3 py3-pip && \
    pip3 --quiet --disable-pip-version-check --no-cache-dir install \
        Jinja2 \
        jsonschema \
        PyYAML \
        emoji \
        ansicolors
ARG VERSION="0.0.0"
RUN mkdir -pv /deployster && echo "${VERSION}" > /deployster/VERSION
ENV PYTHONPATH="/deployster/lib"
ENV PYTHONUNBUFFERED="1"
COPY src /deployster/lib
RUN chmod a+x /deployster/lib/deployster.py
ENTRYPOINT ["/deployster/lib/deployster.py"]
