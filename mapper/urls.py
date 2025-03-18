from django.conf.urls import url
from django.views.decorators.cache import cache_page
from . import views

urlpatterns = [
    url(r'^DataMapperHome(?P<page>\w+)/$', views.DataMapperHome.as_view(), name='DataMapperHome'),
    url(r'^plotrender', views.plotrender.as_view(), name='data_mapper_plotrender')
]
