"""serviceform_project URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

#from django.shortcuts import render
#handler403 = lambda request: render(request, 'serviceform/error/403.html')
#handler404 = lambda request: render(request, 'serviceform/error/404.html')
#handler500 = lambda request: render(request, 'serviceform/error/500.html')

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^_grappelli/', include('grappelli.urls')),
    url(r'^_nested_admin/', include('nested_admin.urls')),
    url(r'^_select2/', include('select2.urls')),
    url(r'', include('serviceform.serviceform.urls')),
]
if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

admin.site.site_header = admin.site.site_title = _('Serviceform admin')
