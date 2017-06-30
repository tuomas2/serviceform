FROM tuomasairaksinen/serviceform-base:latest
MAINTAINER Tuomas Airaksinen <tuomas.airaksinen@gmail.com>
ADD ./requirements.txt /
RUN pip install -r requirements.txt
ADD . /code/
WORKDIR /code
RUN mkdir /code/static
RUN DOCKER_BUILD=1 ./manage.py collectstatic --noinput
RUN DOCKER_BUILD=1 ./manage.py compress
ARG VCS_REF
RUN echo $VCS_REF > .git_sha
EXPOSE 8080
USER web
ENTRYPOINT ["bash", "-x", "entrypoint.sh"]
ARG VERSION
ARG BUILD_DATE
LABEL org.label-schema.vcs-ref=$VCS_REF \
      org.label-schema.vcs-url="e.g. https://github.com/tuomas2/serviceform" \
      org.label-schema.version=$VERSION \
      org.label-schema.build-date=$BUILD_DATE \
      org.label.schema-version="1.0"
