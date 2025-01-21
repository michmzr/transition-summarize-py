# Readme
## Database setup

#### First Time Setup
1. Initialize Alembic (if not done before):
```bash
alembic init alembic
```

2. Initialize the database schema:
```bash
alembic stamp head
```

3. Run the initial migration:
```bash
alembic upgrade head
```

#### Create a new migration:
1. Create a new migration:
```bash
alembic revision --autogenerate -m "migration name"
```

2. Apply pending migrations:
```bash
alembic upgrade head
```

3. Check migration status:
```bash
alembic current
```

```bash
alembic history
```

#### Troubleshooting

If you need to reset the database:
1. Drop all tables:
```bash
alembic downgrade base
```

2. Reapply all migrations:
```bash
alembic upgrade head

## Running the Application

#### Local Development
1. Start the database:
```bash
docker-compose --env-file ./.env -f ./deploy/docker-compose.yml up 
```

2. Ensure database schema is up to date:
```bash
alembic upgrade head
```

3. Run the application:
```bash
uvicorn main:app --reload
```

## Tests
### Integration Tests
```bash
pipenv run pytest tests/integration -v
```

**Run with coverage:**
```bash
pipenv run pytest tests/integration -v --cov=app --cov-report=term-missing
```