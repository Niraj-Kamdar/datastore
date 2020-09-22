# Datastore

This is a REST API service which allows upload and download of data with ability to pause, resume and abort. You can try it live on [data-store-api.herokuapp.com](https://data-store-api.herokuapp.com/).

> Note: Above site is just for demonstation purpose and do not upload large file to it. Any task that runs more than 10 minutes will be aborted.

## Getting Started
These instructions will get you a copy of the project up and running on your local machine for development and testing purposes. If you want to use it in production you can skip to the deployment section.

### Prerequisites

- python 3.8 
- memcached 
- pipenv

### Installing
After cloning/downloading this repository you have to install necessary packages from Pipfile with following command

```console
pipenv install
```

This will install all dependencies needed to run the server.

### Starting server

After installation you just need to run following command to start server.

```console
uvicorn app.main:app
```
> You can stop server by pressing ctrl+c.

## Deployment

If you want to deploy this application. You can do this easily by running following command

```console
docker-compose up
```

This will build docker image and will start all required services to run server. You can visit server on `localhost:80`.
