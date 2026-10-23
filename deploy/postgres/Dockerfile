FROM postgres:16
COPY deploy/postgres/init-dev.sh /docker-entrypoint-initdb.d/01-init-dev.sh
RUN chmod 755 /docker-entrypoint-initdb.d/01-init-dev.sh
