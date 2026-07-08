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

## API Documentation (Swagger / OpenAPI)

FastAPI udostępnia dokumentację API automatycznie — nie trzeba nic osobno instalować ani uruchamiać.

Po starcie aplikacji (`uv run -m app`) dokumentacja jest dostępna pod:

| Co | URL (domyślny port 8000) |
|---|---|
| Swagger UI | http://127.0.0.1:8000/docs |
| ReDoc | http://127.0.0.1:8000/redoc |
| OpenAPI JSON | http://127.0.0.1:8000/openapi.json |

Chronione endpointy są zamontowane pod `/api` — ich dokumentacja:

| Co | URL |
|---|---|
| Swagger UI | http://127.0.0.1:8000/api/docs |
| OpenAPI JSON | http://127.0.0.1:8000/api/openapi.json |

Przy innym porcie (np. `PORT=8086`) zamień `8000` na właściwy numer.

### Autoryzacja w Swagger UI

Większość endpointów wymaga tokenu JWT:

1. Wywołaj `POST /auth/token` z username i password.
2. Kliknij **Authorize** w Swagger UI.
3. Wklej token w formacie `Bearer <token>`.

Token jest zapamiętywany w sesji Swaggera (`persistAuthorization`).

## Tests
### Integration Tests
```bash
uv run pytest tests/integration -v
```

**Run with coverage:**
```bash
uv run pytest tests/integration -v --cov=app --cov-report=term-missing
```
