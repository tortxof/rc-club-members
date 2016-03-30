# rc-club-members

## A flask app for managing members of an RC club.

## Installation

You can deploy this app with [Docker](https://www.docker.com/). The Docker image
runs a uwsgi server speaking uwsgi by default. For deployment you'll need nginx
to reverse proxy. To run a development server that speaks HTTP, see the section
below about running in development mode.

When running the Docker container, set the `APP_URL` environment variable to the
url of the app, without the trailing `/`. For example
`APP_URL=https://members.example.com`.

To send email from the app using mailgun, provide your mailgun domain and key by
setting environment variables in docker.

Flask also needs a `SECRET_KEY`. If one is not provided it will be randomly
generated. If `SECRET_KEY` changes, login sessions and ro tokens will become
invalid, so it should be provided. You can run `gen_keys.py` to have several
keys generated for you.

    docker run --rm tortxof/rc-club-members python gen_keys.py

### Docker

Pull the image from Docker Hub and run it.

    docker pull tortxof/rc-club-members
    docker run -d --restart always --name rc-club-members \
      -v /host/path/to/data:/members-data
      -e APP_URL=https://members.example.com \
      -e MAILGUN_DOMAIN=example.com \
      -e MAILGUN_KEY=key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx \
      -e SECRET_KEY=EXAMPLE_DO_NOT_USE_IN_PRODUCTION
      -p 5000:5000 tortxof/rc-club-members

### Nginx

This is the setup I recommend for nginx. This is setup on the host machine, not
in the docker container. You should of course change the domain names and SSL
files. This will redirect any http requests to the https server. Copy the
following to `/etc/nginx/sites-available/rc-club-members` and symlink to it from
`/etc/nginx/sites-enabled/rc-club-members`.

    server {
      listen 80;
      server_name members.example.com;
      return 301 https://members.example.com$request_uri;
    }

    server {
      listen 443;
      ssl on;
      server_name members.example.com;
      ssl_certificate /etc/nginx/ssl/members.example.com.crt;
      ssl_certificate_key /etc/nginx/ssl/members.example.com.key;

      location / {
        uwsgi_pass localhost:5000;
        include /etc/nginx/uwsgi_params;
      }
    }

### Setup Database

Once the app is up and running, go to `/setup` in your browser to create the
first user. As long as the database file does not exist, the app will let you
create a user.

## Upgrading

To upgrade, pull a new image from Docker Hub, remove the old container, and run
a new one.

    docker pull tortxof/rc-club-members
    docker rm $(docker stop rc-club-members)
    docker run -d --restart always --name rc-club-members \
      -v /host/path/to/data:/members-data
      -e APP_URL=https://members.example.com \
      -e MAILGUN_DOMAIN=example.com \
      -e MAILGUN_KEY=key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx \
      -e SECRET_KEY=EXAMPLE_DO_NOT_USE_IN_PRODUCTION
      -p 5000:5000 tortxof/rc-club-members


## Build Your Own image

If you don't want to pull the image from Docker Hub, you can build it yourself.

    git clone https://github.com/tortxof/rc-club-members.git
    cd rc-club-members
    docker build -t tortxof/rc-club-members .

It's also possible to have docker pull the git repo itself.

    docker build -t tortxof/rc-club-members https://github.com/tortxof/rc-club-members.git

## Run In Development Mode

With Flask in debug mode, it will auto restart when changes are detected.
The `FLASK_DEBUG` environment variable puts Flask in debug mode.
The `python members.py` command at the end overrides the default uwsgi command.
To start a container in debug mode, run this command from the root of the git
repo.

    docker run -d --name rc-club-members \
      -e FLASK_DEBUG=true \
      -v $(pwd):/app \
      -p 5000:5000 \
      tortxof/rc-club-members python members.py

This will mount the git repo from the host to `/app` in the container,
overriding the containers built in app.
