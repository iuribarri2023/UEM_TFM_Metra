# Soluciones genéricas — corpus activo METRA-DEMO

Esta carpeta incluye los manifiestos JSON de **94 soluciones genéricas activas** y sus IFC asociados. Los arquetipos y códigos se identifican mediante `taxonomy.json`; ese registro taxonómico puede reservar códigos de categorías previamente retiradas, que no se importan como soluciones activas.

La versión de esquema de los manifiestos es un **contrato técnico**, independiente de la nomenclatura de las carpetas. La estructura de códigos de solución se conserva para mantener las relaciones entre soluciones genéricas, productos comerciales y bases PostgreSQL existentes.

La validez operativa se comprueba con `backend/scripts/catalogue_data.py validate` e `inventory.json`. Los valores ilustrativos se identifican como estimaciones y no se atribuyen a declaraciones certificadas de fabricante.
