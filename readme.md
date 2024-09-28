
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