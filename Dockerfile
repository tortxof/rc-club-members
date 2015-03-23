FROM ubuntu:trusty
MAINTAINER Daniel Jones <tortxof@gmail.com>

ENV USE_DOCKER_CONFIG TRUE

RUN apt-get update && apt-get -y dist-upgrade
RUN apt-get install -y python3-setuptools git-core sqlite3 nano
RUN easy_install3 pip
RUN git clone https://github.com/tortxof/rc-club-members.git /app
RUN pip3 install -r /app/requirements.txt

WORKDIR /app

EXPOSE 5000

CMD ["python3", "members.py"]
