FROM google/cloud-sdk:171.0.0
MAINTAINER Arik Kfir <arik@infolinks.com>
ADD bin /deploy/bin
RUN chmod a+x /deploy/bin/*.py && \
    mkdir -p /deploy/staging
RUN apt-get update -qqy && apt-get install -qqy jq && rm -rf /var/lib/apt/lists/* && \
    pip --quiet --disable-pip-version-check --no-cache-dir install \
        google-api-python-client \
        Jinja2 \
        jsonmerge \
        python-dateutil \
        subprocess32
WORKDIR /deploy/staging
ENTRYPOINT ["/deploy/bin/apply.sh"]
