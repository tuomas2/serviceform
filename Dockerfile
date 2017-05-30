FROM tuomasairaksinen/serviceform-base:latest
MAINTAINER Tuomas Airaksinen <tuomas.airaksinen@gmail.com>
ADD ./requirements.txt /
RUN pip install -r requirements.txt
ADD . /code/
WORKDIR /code
RUN git rev-parse HEAD > .git_sha
RUN apk del git
RUN rm -r .git
RUN mkdir /code/static
RUN DOCKER_BUILD=1 ./manage.py collectstatic --noinput
RUN DOCKER_BUILD=1 ./manage.py compress
# Tests need these
RUN mkdir .cache
RUN touch .coverage
RUN chmod a+rw .cache .coverage
# WSGI port defined in uwsgi.ini
EXPOSE 9051
USER web
ENTRYPOINT ["bash", "-x", "entrypoint.sh"]
