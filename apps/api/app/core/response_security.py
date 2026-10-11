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
            await send(message)

        await self.app(scope, receive, secured_send)
