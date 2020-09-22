# Datastore

This is a REST API service which allows upload and download of data with ability to pause, resume and abort. You can try it live on [data-store-api.herokuapp.com](https://data-store-api.herokuapp.com/).

> Note: Above site is just for demonstation purpose and do not upload large file to it. Any task that runs more than 10 minutes will be aborted.

## Usage

You can see documentation of API in both [swagger](https://data-store-api.herokuapp.com/docs) and [redoc](https://data-store-api.herokuapp.com/redoc) style. You need to first create an account which is very easy and free. You need to use basic authorization for all other requests. 

### How to upload/download a file
- Create a task using POST request to `/create_task`
- Upload file using PUT request to `/upload_file/{task_id}` endpoint. Here, task_id can be found in response of the first request.

This will start uploading your file to datastore. You can also pause, resume or abort upload of this file using `/pause_task/{task_id}`, `/resume_task/{task_id}` or `/abort_task/task_id` endpoints.

> Note: You can only upload one file at a time currently.

To download a file you also need to create a task and then you can download file by GET request to `download_file/{task_id}` endpoint. By default it will download every file of the user. You can specify any valid regex in `filename` query and/or you can download file that are uploaded in the time between `from_date` and `to_date`. Files are downloaded in zip format. You can also pause, resume or abort download of a file.

You can also delete files similarly like you can download file using DELETE method on `delete_file{task_id}` endpoint.

## How it works

Whenever a user requests to create a task. It will create a random unique `task_id` which maps to the current state of the task (EX: paused, resumed etc.) This mapping are stored in memcached for 24 hours (by default but can be configured by the admin). While downloading or uploading file(s) system frequently check for latest state of the task. If user changes the state of task to pause it will pause the task and resumes it when task changes back to resume. If user abort the task, system will simply delete the mapping and stop the task associated with it. It will also stop the task if mapping expires. The system will release every resources occupied for the task when task get aborted.

> The system is scalable because of the use of **memcached** to store state of the task. If we store this state in server memory. It won't work as expected in case of multiple servers.
 
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
