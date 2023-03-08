FROM python:latest
RUN apt-get update -y

WORKDIR /opt/app/

COPY app.py requirements.txt ./
COPY images/ ./images/
COPY static/ ./static/
COPY templates/ ./templates/

RUN pip install -r ./requirements.txt

ARG POSTGRES_PASSWORD
ARG RABBITMQ_DEFAULT_PASS

ENV DB_NAME=iotdata
ENV POSTGRES_USER=postgres
ENV RABBITMQ_DEFAULT_USER=RABBITMQ_DEFAULT_USER

ENV POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
ENV RABBITMQ_DEFAULT_PASS=${RABBITMQ_DEFAULT_PASS}

ENV ENVIRONMENT=production

EXPOSE 80

CMD [ "python", "app.py" ]
