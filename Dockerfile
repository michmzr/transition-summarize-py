FROM python:3
WORKDIR /code

COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./app /code/app

CMD ["ls", "-la"]
CMD ["fastapi", "run", "app/main.py", "--port", "8086", "--proxy-headers"]