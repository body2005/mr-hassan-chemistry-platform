"""Security headers also cover admission, CORS and early rejection responses."""
from starlette.datastructures import MutableHeaders


class ResponseSecurityHeadersMiddleware:
    def __init__(self, app, *, secure: bool):
        self.app = app
        self.headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'SAMEORIGIN',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
        }
        if secure:
            self.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            self.headers['Content-Security-Policy'] = "default-src 'self'; frame-ancestors 'self'"

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def secured_send(message):
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(scope=message)
                for name, value in self.headers.items():
                    headers.setdefault(name, value)
                # Personal JSON, files, early errors and SSE must never be
                # reused for another cookie/account by a shared proxy cache.
                if scope.get('path', '').startswith('/api/'):
                    headers['Cache-Control'] = ('private, no-store, no-transform'
                        if 'no-transform' in headers.get('Cache-Control', '') else 'private, no-store')
                    vary = {part.strip() for part in headers.get('Vary', '').split(',') if part.strip()}
                    vary.update(('Cookie', 'Authorization'))
                    headers['Vary'] = ', '.join(sorted(vary))
            await send(message)

        await self.app(scope, receive, secured_send)
