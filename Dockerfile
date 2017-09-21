FROM google/cloud-sdk:171.0.0-alpine
MAINTAINER Arik Kfir <arik@infolinks.com>
ADD bin /deploy/bin
RUN chmod a+x /deploy/bin/*.py && \
    mkdir -p /deploy/staging
RUN apk --no-cache --update add jq py2-pip && \
    gcloud components install --quiet kubectl && \
    pip --quiet --disable-pip-version-check --no-cache-dir install \
        google-api-python-client \
        Jinja2 \
        jsonmerge \
        python-dateutil
WORKDIR /deploy/staging
ENTRYPOINT ["/deploy/bin/deploy.sh"]
