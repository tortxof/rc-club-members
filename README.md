rc-club-members
===============

A flask app for managing members of an RC club.
-----------------------------------------------

Installation
------------

You can deploy this app with [Docker](https://www.docker.com/) or
[upstart](http://upstart.ubuntu.com/)/[virtualenv](https://virtualenv.pypa.io/).
Either way, you should setup a reverse proxy with nginx.

### Docker

First we need a
[data container](https://docs.docker.com/userguide/dockervolumes/#creating-and-mounting-a-data-volume-container)
to keep the database file.

    sudo docker create -v /members-data --name members_data ubuntu:trusty

This container will not run any processes. It's only for holding our database
file. We will connect it to our app container later using the `--volumes-from`
command line option.

Now let's clone the git repository. This directory will be bound to the app container.

    git clone https://github.com/tortxof/rc-club-members.git

Next we will build the docker image.

    cd rc-club-members
    sudo docker build -t "tortxof/rc-club-members" .

This process may take a few minutes. Next, we can run an app container. To use a
port other than 5000, change the first number in the `-p` option. For example,
to use port 80, `-p 80:5000`.

    sudo docker run -d --restart always --volumes-from members_data -v $(pwd):/app --name members_app -p 5000:5000 tortxof/rc-club-members

Now the app should be up and running. You can check with `docker ps`.

    sudo docker ps

### Upstart

More info coming soon.

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

### Upgrading

To upgrade, we will use docker exec to run the upgrade script, then restart the
container.

    sudo docker exec members_app ./upgrade.sh
    sudo docker restart members_app
