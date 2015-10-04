# rc-club-members

## A flask app for managing members of an RC club.

## Installation

You can deploy this app with [Docker](https://www.docker.com/).
The Docker image runs a uwsgi server speaking uwsgi by default.
For deployment you'll need nginx to reverse proxy.
To have the uwsgi server speak HTTP, see the section below about running in
development mode.

### Docker

Pull the image from Docker Hub and run it.

    docker pull tortxof/rc-club-members
    docker run -d --restart always --name members-app -p 5000:5000 tortxof/rc-club-members

Then create a
[data container](https://docs.docker.com/userguide/dockervolumes/#creating-and-mounting-a-data-volume-container)
to keep the database and key files.

    docker create --name members-data --volumes-from members-app busybox

See below for upgrading if you already have a data container.

### Mailgun

To be able to send email, you must provide a `/members-data/mailgun.json` file
with your mailgun `domain` and API `key`. Don't forget to set ownership and
permissions the same as `/members-data/key`.

    {
      "domain": "example.com",
      "key": "key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    }

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
    docker rm $(docker stop members-app)
    docker run -d --restart always --volumes-from members-data --name members-app -p 5000:5000 tortxof/rc-club-members

## Build Your Own image

If you don't want to pull the image from Docker Hub, you can build it yourself.

    git clone https://github.com/tortxof/rc-club-members.git
    cd rc-club-members
    docker build -t tortxof/rc-club-members .

## Run In Development Mode

With Flask in debug mode, it will auto restart when changes are detected.
The `FLASK_DEBUG` environment variable puts Flask in debug mode.
The `UWSGI_HTTP` environment variable tells the uwsgi server to spawn an HTTP
server. To start a container in debug mode, run this command from the root of
the git repo.

    docker run -d --name members-app --volumes-from members-data -e FLASK_DEBUG=true -e UWSGI_HTTP=0.0.0.0:4000 -p 8080:4000 -v $(pwd):/app tortxof/rc-club-members

This will mount the git repo from the host to `/app` in the container,
overriding the containers built in app.
