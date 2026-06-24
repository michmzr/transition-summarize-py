# Readme
## Database setup

#### First Time Setup
1. Initialize Alembic (if not done before):
```bash
uv alembic init alembic
```

2. Initialize the database schema:
```bash
uv alembic stamp head
```

3. Run the initial migration:
```bash
uv alembic upgrade head
```

#### Create a new migration:
1. Create a new migration:
```bash
uv alembic revision --autogenerate -m "migration name"
```

2. Apply pending migrations:
```bash
uv alembic upgrade head
```

3. Check migration status:
```bash
uv alembic current
```

```bash
uv alembic history
```

#### Troubleshooting

If you need to reset the database:
1. Drop all tables:
```bash
uv alembic downgrade base
```

2. Reapply all migrations:
```bash
uv alembic upgrade head
```

## Running the Application

#### Local Development
1. Start the database:
```bash
docker-compose --env-file ./.env -f ./deploy/docker-compose.yml up
```

2. Ensure database schema is up to date:
```bash
uv alembic upgrade head
```

3. Run the application:
```bash
uv run -m app
```

Domyślnie serwer startuje na `http://127.0.0.1:8000` z automatycznym relodem przy zmianach w katalogu `app/`.
Port i host można nadpisać zmiennymi środowiskowymi:
```bash
HOST=0.0.0.0 PORT=8086 uv run -m app
```

## Tests
### Integration Tests
```bash
uv run pytest tests/integration -v
```

**Run with coverage:**
```bash
uv run pytest tests/integration -v --cov=app --cov-report=term-missing
```
