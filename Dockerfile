FROM python:3.11
WORKDIR /code

# fast api set dev mode
ARG DEV_MODE=""

COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./app /code/app

CMD "ls -la"
RUN fastapi $DEV_MODE run app/main.py --port 8086
