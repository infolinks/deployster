FROM alpine:3.6
MAINTAINER Arik Kfir <arik@infolinks.com>
RUN apk --no-cache --update add bash docker jq python3 py3-pip && \
    pip3 --quiet --disable-pip-version-check --no-cache-dir install \
        Jinja2 \
        jsonschema \
        PyYAML \
        emoji \
        ansicolors
ENV PYTHONPATH="/deployster/lib:$PYTHONPATH"
COPY src /deployster/lib
RUN chmod a+x /deployster/lib/deployster.py
WORKDIR /deployster/workspace/
ENTRYPOINT ["/deployster/lib/deployster.py"]
