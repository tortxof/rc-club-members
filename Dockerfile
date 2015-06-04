FROM python:3.4
MAINTAINER Daniel Jones <tortxof@gmail.com>

RUN mkdir /app
WORKDIR /app
COPY . /app
RUN pip install -r requirements.txt

ENV USE_DOCKER_CONFIG TRUE

EXPOSE 5000

CMD ["python3", "./members.py"]
