FROM markwatsonatx/pixiedust-base-python35:latest

MAINTAINER Mark Watson <markwatsonatx@gmail.com>

WORKDIR /home/root
ADD startup.sh ./

RUN mkdir -p /root/pixiedust/bin

RUN apt-get update
RUN apt-get install libgconf2-4 libnss3-1d libasound2 libgtk-3-0 libx11-xcb1 libxtst6 --assume-yes
RUN apt-get install libxss1 libappindicator1 libindicator7 fonts-liberation lsb-release xdg-utils --assume-yes
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN apt-get install -f --assume-yes
RUN dpkg -i google-chrome*.deb

WORKDIR /

WORKDIR /pixiedust
#RUN pip install -e ./
#RUN jupyter pixiedust install --silent --spark=2.1.0
#RUN jupyter pixiedust install --silent --spark=2.0.2
#RUN jupyter pixiedust install --silent --spark=1.6.3
#RUN cp /root/pixiedust/notebooks/*.ipynb /usr/notebooks
