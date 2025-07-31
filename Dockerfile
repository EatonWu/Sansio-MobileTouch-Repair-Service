# syntax=docker/dockerfile:1

FROM python:bullseye
LABEL authors="ewu"

# execute server/data_collection_server.py
WORKDIR /app

## install dependencies
COPY . .
#RUN ls
RUN python3 -m pip install --no-cache-dir -r server/requirements.txt
#CMD ["python", "server/data_collection_server.py"]

ENTRYPOINT ["python", "server/data_collection_server.py"]

# Expose port 5000
EXPOSE 5000