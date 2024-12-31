
## Run

### Local 

#### First time

```bash
alembic init alembic
```

#### Run 
**Databse run from docker compose in the project root**
```bash
docker-compose --env-file ./.env -f ./deploy/docker-compose.yml up 
```

**Update db:**
```bash
alembic upgrade head
```

## DB 
**Init DB:**
```bash
alembic stamp head
```

**New migration:**
```bash
alembic revision --autogenerate -m "migration name"
```
