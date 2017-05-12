FROM python:3.6.1-alpine
ENV PYTHONUNBUFFERED 1
RUN apk update && apk upgrade && apk add --no-cache gettext postgresql-dev gcc g++ make linux-headers python3-dev musl-dev postgresql-client bash
RUN pip install --upgrade pip setuptools
RUN mkdir /code
ADD ./requirements.txt /
RUN pip install -r requirements.txt
RUN adduser -D web
ADD . /code/
WORKDIR /code
RUN mkdir /code/static
RUN apk del postgresql-dev make linux-headers python3-dev
# Tests need these
RUN mkdir .cache
RUN touch .coverage
RUN chmod a+rw .cache .coverage
VOLUME /code/static
# WSGI port defined in uwsgi.ini
EXPOSE 9051
USER web
ENTRYPOINT ["bash", "-x", "entrypoint.sh"]
