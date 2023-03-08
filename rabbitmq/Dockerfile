FROM rabbitmq:3-management
RUN apt-get update -y

COPY ./definitions.json /etc/rabbitmq/
ADD ./init.sh /init.sh
RUN chmod +x ./init.sh

ARG RABBITMQ_DEFAULT_USER="rabbitmq_user"
ARG RABBITMQ_DEFAULT_PASS

ENV RABBITMQ_DEFAULT_USER=${RABBITMQ_DEFAULT_USER}
ENV RABBITMQ_DEFAULT_PASS=${RABBITMQ_DEFAULT_PASS}
ENV RABBITMQ_PID_FILE /var/lib/rabbitmq/mnesia/rabbitmq

EXPOSE 15672
EXPOSE 5672

CMD '/init.sh'