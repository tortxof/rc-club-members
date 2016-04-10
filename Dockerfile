FROM python:3.4
MAINTAINER Daniel Jones <tortxof@gmail.com>

RUN groupadd -r app && useradd -r -g app app

COPY requirements.txt /app/
WORKDIR /app
RUN pip install -r requirements.txt
COPY . /app/

RUN mkdir /data && chown app:app /data

USER app

VOLUME ["/data"]

EXPOSE 5000

CMD ["uwsgi", "--yaml", "uwsgi.yaml"]
