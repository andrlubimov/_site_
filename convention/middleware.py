from django.conf import settings
from django.http.request import split_domain_port

SITE_URLCONF = 'convention.site_urls'


class ConventionSiteMiddleware:
    """Сайт конвенции на своём домене (settings.CONVENTION_HOSTS): тот же сервер и база, но свои адреса —
    convention.site_urls. Остальной сайт и админка на этом домене не открываются.
    На любом домене, кроме настоящего (settings.CONVENTION_PUBLIC_HOST), — запрет индексации: временный домен
    для наполнения не попадёт в поиск."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.hosts = {host.lower() for host in settings.CONVENTION_HOSTS}
        self.public_host = settings.CONVENTION_PUBLIC_HOST.lower()

    def __call__(self, request):
        domain, _ = split_domain_port(request.get_host())
        if domain not in self.hosts:
            return self.get_response(request)
        request.urlconf = SITE_URLCONF
        request.convention_preview = domain != self.public_host
        response = self.get_response(request)
        if request.convention_preview:
            response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
