#FROM ubuntu:20.04
FROM python:3.9
SHELL ["/bin/bash","-x","-e","-c"]
RUN apt-get -y update
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get -y install libssl-dev g++ graphviz-dev libtool make automake autoconf libsqlite3-dev libpython3-dev libyaml-dev libcurl4 dnsutils nano graphviz gcc jq libjq-dev git wget libpq-dev curl dnsutils nano docker dos2unix uuid-runtime zlib1g-dev
RUN cd /opt; wget https://www.python.org/ftp/python/3.9.6/Python-3.9.6.tgz; tar -zxvf Python-3.9.6.tgz; cd Python-3.9.6; ./configure && make -j16 && make install
RUN pip3 install virtualenv
RUN virtualenv -p $(which python3) /opt/venv
ADD ./ /opt/sprout
WORKDIR /opt/sprout
RUN source /opt/venv/bin/activate && python3 setup.py install
