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

Now let's clone the git repository. This can be done in the home directory. It
will not be needed once everything is up and running.

    git clone https://github.com/tortxof/rc-club-members.git

Next we will build the docker image.

    cd rc-club-members
    sudo docker build .

This process may take a few minutes.

    sudo docker run -d --restart always --volumes-from members_data --name members_app -p 5000:5000

### Upstart
