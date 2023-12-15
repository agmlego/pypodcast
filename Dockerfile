FROM python:3
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

VOLUME /data
ENV PYPODCAST_DATA=/data