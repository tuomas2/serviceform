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
EXPOSE 8080
USER web
ENTRYPOINT ["bash", "-x", "entrypoint.sh"]
