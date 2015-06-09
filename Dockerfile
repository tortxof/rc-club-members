FROM python:3.4
MAINTAINER Daniel Jones <tortxof@gmail.com>

RUN groupadd -r app && useradd -r -g app app

COPY requirements.txt /app/
WORKDIR /app
RUN pip install -r requirements.txt
COPY . /app/

RUN mkdir /members-data && chown app:app /members-data

USER app

VOLUME ["/members-data"]

EXPOSE 5000

CMD ["uwsgi", "--yaml", "uwsgi.yaml"]
