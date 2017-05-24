FROM tuomasairaksinen/serviceform-base:latest
MAINTAINER Tuomas Airaksinen <tuomas.airaksinen@gmail.com>
ADD ./requirements.txt /
RUN pip install -r requirements.txt
ADD . /code/
WORKDIR /code
RUN mkdir /code/static
# Tests need these
RUN mkdir .cache
RUN touch .coverage
RUN chmod a+rw .cache .coverage
VOLUME /code/static
# WSGI port defined in uwsgi.ini
EXPOSE 9051
USER web
ENTRYPOINT ["bash", "-x", "entrypoint.sh"]
