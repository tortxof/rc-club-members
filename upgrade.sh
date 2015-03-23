#! /bin/bash

apt-get update && apt-get -y dist-upgrade

git checkout master
git pull

pip3 install --upgrade -r requirements.txt
