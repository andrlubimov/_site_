from django.conf import settings
from django.http.request import split_domain_port

SITE_URLCONF = 'convention.site_urls'


class ConventionSiteMiddleware:
    """Сайт конвенции на своём домене (settings.CONVENTION_HOSTS): тот же сервер и база, но свои адреса —
    convention.site_urls. Остальной сайт и админка на этом домене не открываются."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.hosts = {host.lower() for host in settings.CONVENTION_HOSTS}

    def __call__(self, request):
        domain, _ = split_domain_port(request.get_host())
        if domain in self.hosts:
            request.urlconf = SITE_URLCONF
        return self.get_response(request)
