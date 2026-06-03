#Django Framework imports
from django.http import JsonResponse

#Rest Framework imports
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.pagination import LimitOffsetPagination

#Table provider imports
from table_provider.configuration_provider.configuration_factory import ColumnConfigurationFactory, DataTablesConfigurationFactory
from table_provider.models import StructureModelStatisticsTable
from table_provider.serializers import StatisticsSummarySerializer
from table_provider.serverside.filters import *
from table_provider.serverside.querystringprocessing import datatablesQueryStringProcessor
from structure.tables.structure_coverage_model_statistics_query import StructureCoverageModelStatisticsQuery

#Pagination handler for dataTables server side processing
class DataTablesLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 30
    max_limit = 200
    limit_query_param = "length"  
    offset_query_param = "start"  

class StructureStatisticsSummaryTable(generics.ListCreateAPIView):
    """
    Get general summary statistics for GPCR entries 
    \n/statistics_table/{database}/
    \n{database} is one of gpcr, gprotein, or arrestin
    """
    database = None
    
    #############
    # API setup #
    #############

    serializer_class = StatisticsSummarySerializer
    pagination_class = DataTablesLimitOffsetPagination

    def get_queryset(self):
        filters = FilterSet(self.request, StatisticsSummarySerializer)
        queryset = self.statistics_table_fetch(self.database, filters)
        return queryset

    def list(self, request, *args, **kwargs):
        self.database = self.kwargs.get('database')
        
        unfilteredCount = StructureModelStatisticsTable.objects.all().count()
        
        if StructureModelStatisticsTable.objects.all().count() == 0:
            self.BuildStatisticsSummaryTable()
            unfilteredCount = StructureModelStatisticsTable.objects.all().count()
        
        queryset = self.get_queryset()
        url_params = datatablesQueryStringProcessor(self.request).query_set 

        # server side datatables processing response format
        if 'draw' in url_params:

            response = {}
            
            rows = list(queryset)  # Default to full queryset if pagination is not applied
            
            # unfilteredCount = self.fetchQueryMaxResultCount()
            filteredCount = len(rows)
            
            page = self.paginate_queryset(rows)
            if page is not None:
                rows = page
                
            serializer = self.get_serializer(rows, many=True)  
            
            response["draw"] = url_params["draw"]
            response["recordsTotal"] = unfilteredCount
            response["recordsFiltered"] = filteredCount
            response["data"] = serializer.data        
            
            return JsonResponse(response)
        
        else:
            # client side datatables processing response format
            serializer = self.get_serializer(queryset, many=True)  
            # for consistency with server side processing response format, 
            # wrap data in "data" key, even though client side processing doesn't require this
            response = {}
            response["data"] = serializer.data   
            return Response(response)


    def statistics_table_fetch(self, database, filters):
        
        queryset = StructureModelStatisticsTable.objects.all()

        for query_filter in filters.get_filters():            
            queryset = queryset.filter(**query_filter.format_django())

        if filters.get_ordering():
            queryset = queryset.order_by(*filters.get_ordering())

        return queryset
    

    def BuildStatisticsSummaryTable(self):
        stat_data_model = [ StructureModelStatisticsTable(**data_item) for data_item in StructureCoverageModelStatisticsQuery(self.database) ]
        StructureModelStatisticsTable.objects.bulk_create(stat_data_model, batch_size=10000)




class ConfigurationFactoryView(generics.ListCreateAPIView):
    def get(self, request, *args, **kwargs):
        configuration_type = self.kwargs.get('configuration_type')
        table_name = self.kwargs.get('table_name')
        configuration_variant = self.kwargs.get('configuration_variant')
        
        if configuration_type == 'column':
            config_factory = ColumnConfigurationFactory(table_name, configuration_variant)
        elif configuration_type == 'datatable':
            config_factory = DataTablesConfigurationFactory(table_name, configuration_variant)
        else:
            return JsonResponse({'error': 'Invalid configuration type requested ' + configuration_type}, status=400)
        config = config_factory.fetch()

        return JsonResponse(config, safe=False)