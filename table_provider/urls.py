from django.conf.urls import url
from django.urls import path
from table_provider.views import *
from django.views.decorators.cache import cache_page

urlpatterns = [
    #Non-cached URL for server-side processing
    url(r'^structure_statistics_table/(?P<database>[^/]+)/?$', (StructureStatisticsSummaryTable.as_view()), name='structure_statistics_table'),
    #Cached URL for client side processing
    url(r'^structure_statistics_table_cached/(?P<database>[^/]+)/?$$', cache_page(60*60*24)(StructureStatisticsSummaryTable.as_view()), name='structure_statistics_table_cached'),  

    url(r'^configuration/(?P<configuration_type>[^/]+)/(?P<table_name>[^/]+)/(?P<configuration_variant>[^/]+)/?$', ConfigurationFactoryView.as_view(), name='configuration_factory'),
]