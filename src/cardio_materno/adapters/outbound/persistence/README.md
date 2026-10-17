# adapter outbound: persistence

- `JsonFileThreadRepository`: implementa `ThreadRepository` con un archivo JSON por hilo en `data/threads/` (ADR 0006). Lo usan la consola y la web.
- `sqlite_*.py` (ADR 0015): base SQLite con usuarios e hilos por usuario.
  - `SqliteDatabase`: conexión, esquema versionado y transacciones.
  - `SqliteThreadRepository`: `ThreadRepository` acotado a un usuario.
  - `SqliteUserThreadStore`, `SqliteUserDirectory` y `SqliteChannelLog`: los puertos `UserThreadStore`, `UserDirectory` y `ChannelLog`.
- `trace_codec.py`: serialización de la traza, compartida por los dos formatos.

Ver docs/04-datos/.