"""Barrera de la interfaz web: solo atiende peticiones hechas desde la propia máquina.

La interfaz no tiene usuarios ni contraseñas (ADR 0013 y 0022): la vista del equipo muestra
los chats, las trazas y las alertas de todos los canales. Escuchar solo en loopback no
basta, porque hay tres formas de llegar a ella desde fuera sin cambiar esa configuración:

- un túnel o proxy (p. ej., ngrok) apuntado al puerto de la interfaz;
- una página web externa abierta en el navegador del equipo que hace que su propio dominio
  resuelva a 127.0.0.1 (DNS rebinding);
- una página externa que envía una petición sin cuerpo a la interfaz (CSRF).

Por eso cada petición se rechaza si su `Host` no es local, si trae un `Origin` que no es
local o si trae cabeceras de reenvío. No es un control de acceso: publicar la interfaz en
una red exige autenticación y un ADR propio.
"""

from collections.abc import Awaitable, Callable, Mapping

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

LOCAL_NAMES = frozenset({"127.0.0.1", "localhost", "::1"})
# Cabeceras que agrega un proxy o un túnel al reenviar una petición de otra máquina.
FORWARDING_HEADERS = ("forwarded", "x-forwarded-for", "x-forwarded-host", "x-real-ip")
FORBIDDEN_STATUS = 403
NOT_LOCAL = "Esta interfaz solo se puede usar desde el equipo donde está instalada."
SCHEME_SEPARATOR = "://"
IPV6_OPEN, IPV6_CLOSE = "[", "]"
PORT_SEPARATOR = ":"


def host_name(value: str) -> str:
    """Nombre de máquina de un `Host` o de un `Origin`, sin esquema ni puerto.

    Args:
        value: Por ejemplo "127.0.0.1:8000", "http://localhost:8000" o "[::1]:8000".

    Returns:
        El nombre en minúsculas ("" si el valor está vacío o mal formado).
    """
    host = value.strip().lower().rpartition(SCHEME_SEPARATOR)[2]
    if host.startswith(IPV6_OPEN):
        return host[1:].partition(IPV6_CLOSE)[0]
    return host.partition(PORT_SEPARATOR)[0]


def is_local_request(headers: Mapping[str, str]) -> bool:
    """Indica si la petición se hizo desde la propia máquina y hacia ella.

    Args:
        headers: Cabeceras de la petición (nombres en minúsculas).

    Returns:
        False si el `Host` no es local, si el `Origin` existe y no es local o si la
        petición pasó por un proxy.
    """
    if any(name in headers for name in FORWARDING_HEADERS):
        return False
    if host_name(headers.get("host", "")) not in LOCAL_NAMES:
        return False
    origin = headers.get("origin")
    return origin is None or host_name(origin) in LOCAL_NAMES


def add_local_only_guard(app: FastAPI) -> None:
    """Hace que la aplicación rechace con 403 toda petición que no sea local."""

    @app.middleware("http")
    async def local_only(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Deja pasar solo las peticiones locales."""
        if not is_local_request(request.headers):
            return JSONResponse({"detail": NOT_LOCAL}, status_code=FORBIDDEN_STATUS)
        return await call_next(request)
