# METRA — Catálogo técnico BIM · Trabajo Fin de Máster

METRA es un prototipo académico de ingeniería de software para consultar, comparar y gestionar soluciones constructivas genéricas y productos comerciales, con sus datos técnicos y modelos IFC. No incorpora compra ni pagos.

## Arquitectura

- **Angular 20 y TypeScript**: catálogo público, comparación, visor BIM y portales de fabricantes y administración.
- **Flask y SQLAlchemy**: API REST, autenticación, autorización, publicación, trazabilidad y procesamiento.
- **PostgreSQL 16 / JSONB**: entidades, taxonomía, revisiones, permisos y valores técnicos heterogéneos.
- **IfcOpenShell y volumen documental**: ingestión, extracción, huellas SHA-256 y acceso autorizado a IFC.
- **Alembic y Docker Compose**: migraciones secuenciales y publicación inicial idempotente.

[Arquitectura detallada](docs/ARCHITECTURE_FINAL.md) · [Modelo de datos](docs/DATA_MODEL.md) · [API](docs/API.md)

## Catálogo único: `metra-demo`

La **única fuente constructiva activa** incluida en la entrega es `backend/data/metra-demo/`, con 94 soluciones genéricas, 91 productos comerciales, **185 archivos IFC activos** y 13 plantillas por subsistema. Los registros retirados y sus IFC archivados **no están incluidos**. Los fixtures de pruebas (un IFC, un XML y un BC3) están en `backend/tests/fixtures/` y no se importan al catálogo.

`inventory.json` declara referencias y SHA-256; `academic_values.json`, `asset_identity.json` y `historical_identity.json` son **metadatos técnicos** necesarios para distinguir estimaciones y reconocer la procedencia/identidad de assets. No constituyen otros datasets operativos.

PostgreSQL conserva modificaciones, relaciones, revisiones y auditoría. La reconciliación de tres vías compara la fuente actual, la última fuente aceptada y los datos persistidos, **sin autopublicar ni sobrescribir fichas aprobadas**. Las claves persistentes de archivos mantienen su prefijo interno original por compatibilidad, independientemente del nombre de la carpeta.

## Arranque normal (Windows PowerShell, Docker Desktop)

Abre una terminal en la carpeta que contiene `compose.yaml` y los archivos `.env` existentes:

```powershell
cd "C:\ruta\a\METRA"
docker compose -p metra-tfm up -d --build
docker compose -p metra-tfm ps
docker compose -p metra-tfm logs --tail=100 catalogue-init backend frontend
```

La web está disponible en `http://127.0.0.1:8080` si `METRA_HTTP_PORT` conserva su valor predeterminado; consulta tu archivo existente para conocer el puerto configurado. El proyecto Docker **se llama `metra-tfm`** (`name: metra-tfm` en `compose.yaml`). No se instala ninguna CLI PowerShell específica.

`-p metra-tfm` tiene prioridad sobre `COMPOSE_PROJECT_NAME` del `.env` existente. La instalación `metra-final` y sus volúmenes permanecen independientes; para operarla utiliza expresamente `docker compose -p metra-final`.

```powershell
docker compose -p metra-tfm logs -f backend
docker compose -p metra-tfm restart backend frontend
docker compose -p metra-tfm down
```

`docker compose -p metra-tfm down` no elimina los volúmenes. **No uses `docker compose -p metra-tfm down -v`** para actualizar una base existente. Los `.env` locales permanecen sin modificar y no se incluyen en el ZIP distribuible.

## Comprobaciones y mantenimiento

```powershell
docker compose -p metra-tfm config --quiet
docker compose -p metra-tfm exec backend python scripts/catalogue_data.py validate
docker compose -p metra-tfm exec backend python scripts/catalogue_data.py verify-assets
docker compose -p metra-tfm exec backend python scripts/reconcile_metra_demo.py --dry-run --report -
```

La reconciliación con escritura es una decisión administrativa, una vez revisadas propuestas y conflictos:

```powershell
docker compose -p metra-tfm exec backend python scripts/reconcile_metra_demo.py --apply --report -
```

Para importar sin publicar: `docker compose -p metra-tfm exec backend python scripts/import_metra_demo.py --apply`. El servicio `catalogue-init` realiza la inicialización normal; no es necesario ejecutar el importador manualmente en una primera instalación correcta.

Pruebas locales (fuera de Docker, si se han instalado las dependencias):

```bash
cd backend && python scripts/catalogue_data.py validate && python -m pytest -q
cd ../frontend && npm ci && npm run build && npm run test:unit
```

[Guía Windows y actualización de PostgreSQL](docs/DOCKER_FIRST_BOOT.md) · [Migración y respaldo](docs/POSTGRES_MIGRATION_AND_ROLLBACK.md) · [Informe correctivo](docs/CORRECTIVE_MAINTENANCE_REPORT.md) · [Resultados de pruebas](docs/TEST_RESULTS_FINAL.md)

## Alcance, calidad y derechos

La completitud de la estructura técnica no es verificación experimental. Los datos ilustrativos, calculados, desconocidos o no verificados se identifican como tales. La publicación de una ficha no da automáticamente permiso de ver o descargar sus IFC. La redistribución pública de modelos de fabricantes y documentación de terceros requiere derechos independientes.

La compilación Angular y varias pruebas E2E de Docker/PostgreSQL y visor se ejecutaron en proyectos aislados. Quedan sin ejecutar los escenarios completos de dos fabricantes y los fallos SQL inyectados. Los resultados y límites están registrados en `docs/TEST_RESULTS_FINAL.md`.
