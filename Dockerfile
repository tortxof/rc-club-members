FROM ubuntu:trusty
MAINTAINER Daniel Jones <tortxof@gmail.com>

ENV USE_DOCKER_CONFIG TRUE

RUN apt-get update && apt-get -y dist-upgrade
RUN apt-get install -y python3-setuptools
RUN easy_install3 pip

ADD static /app/static/
ADD templates /app/templates/
ADD *.py /app/
ADD app.conf.docker /app/
ADD requirements.txt /app/

RUN pip3 install -r /app/requirements.txt

WORKDIR /app

EXPOSE 5000

CMD ["python3", "members.py"]
