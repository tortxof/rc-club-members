# rc-club-members

## A flask app for managing members of an RC club.

## Installation

You can deploy this app with [Docker](https://www.docker.com/).
It's a good idea to use nginx as a reverse proxy and https server.

### Docker

First we need a
[data container](https://docs.docker.com/userguide/dockervolumes/#creating-and-mounting-a-data-volume-container)
to keep the database file.

    docker create -v /members-data --name members-data python:3.4

This container will not run any processes. It's only for holding our database
file. We will connect it to our app container later using the `--volumes-from`
command line option.

Now let's pull the image from [Docker Hub](https://registry.hub.docker.com/u/tortxof/rc-club-members/).

    docker pull tortxof/rc-club-members

Once the image is pulled, we can run the app container. To use a
port other than 5000, change the first number in the `-p` option. For example,
to use port 80, `-p 80:5000`.

    docker run -d --restart always --volumes-from members-data --name members-app -p 5000:5000 tortxof/rc-club-members

Now the app should be up and running. You can check with `docker ps`.

    docker ps

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
        proxy_pass http://localhost:5000;
        proxy_set_header Host      $host;
        proxy_set_header X-Real-IP $remote_addr;
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
    docker stop members-app
    docker rm members-app
    docker run -d --restart always --volumes-from members-data --name members-app -p 5000:5000 tortxof/rc-club-members

## Build Your Own image

If you don't want to pull the image from Docker Hub, you can build it yourself.

    git clone https://github.com/tortxof/rc-club-members.git
    cd rc-club-members
    docker build -t rc-club-members .

## Run In Development Mode

With Flask in debug mode, it will auto restart when changes are detected.
To start a container in debug mode, run this command from the root of the git repo.

    docker run -d --name members-app --volumes-from members-data -e FLASK_DEBUG=true -p 8080:5000 -v $(pwd):/app tortxof/rc-club-members

This will mount the git repo from the host to `/app` in the container, overriding the containers built in app.
