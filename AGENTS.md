# Instrucciones para OpenCode / agentes

## Flujo de trabajo (obligatorio)

- Cada vez que hagas un push, **crea también una Pull Request** para revisar los cambios antes de hacer merge a `main`.
- Las descripciones de PR deben usar **puntos cortos y concisos** describiendo lo que se ha hecho. Esto facilita decidir si está bien o no.
- Los commits deben seguir un estilo claro (tema + resumen breve).

## Convenciones del proyecto

- Python 3.10+, tests con `pytest`.
- Usar herramientas dedicadas (edit/read/write/grep) antes que shell cuando sea posible.
- El modo `--fixture` no escribe `estado.json` (para pruebas locales).
- Mantén cambios consistentes con estilo y estructura del código existente.
- Ejecutar tests antes de subir cambios importantes.

## Desarrollo local

```bash
.\venv\Scripts\python.exe -m pytest -q
```
