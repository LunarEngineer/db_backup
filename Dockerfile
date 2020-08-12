FROM ubuntu:20.04 as base

RUN apt-get update && \
    apt-get install -y \
        mariadb-client

FROM python:3.7-slim as pythonbase

COPY requirements.txt /
RUN pip install --prefix="/install" -r /requirements.txt

FROM pythonbase

# Some friendly defaults
ENV DLY_BACKUP_COUNT=5 \
    WLY_BACKUP_COUNT=5 \
    MLY_BACKUP_COUNT=5

COPY --from=pythonbase /install /usr/local
COPY --from=base /usr/bin/mysqldump /usr/bin/mysqldump

COPY code /backup_tool

RUN mkdir /backups

ENTRYPOINT [ "/usr/local/bin/python" ,"/backup_tool/db_backup.py"]