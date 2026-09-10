# Seguridad y privacidad

## Lo que hace Moneta

- Aislamiento por usuario en cada consulta, también en MCP.
- Tokens MCP guardados como hash (HMAC-SHA256 con pepper).
- Aprobación humana para todo lo que llega de fuera.
- Protección CSRF y sin efectos de escritura en GET.
- Límite de intentos de login y auditoría de llamadas MCP.

## Lo que debes configurar tú

- `DJANGO_DEBUG=0` y `DJANGO_SECRET_KEY` privada de 50+ caracteres.
- `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS` con tu dominio.
- HTTPS obligatorio; endpoint MCP HTTP en loopback o tras proxy autenticado.
- Copias de seguridad de la base de datos.

## Notas

Para reportar una vulnerabilidad sigue [`../../SECURITY.md`](../../SECURITY.md); no abras una incidencia pública.

---

Versión corta dentro de la app: **Ayuda** en Moneta. Índice: [README.md](README.md).
