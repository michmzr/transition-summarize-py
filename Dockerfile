FROM python:3
WORKDIR /code

# Copy the Pipfile and Pipfile.lock
COPY ./Pipfile /code/Pipfile
COPY ./Pipfile.lock /code/Pipfile.lock
COPY ./app /code/app

RUN pip install --no-cache-dir --upgrade pipenv
RUN pipenv install --system --deploy

# Expose the port
EXPOSE 8086

CMD ["fastapi", "run", "app/main.py", "--port", "8086", "--proxy-headers"]