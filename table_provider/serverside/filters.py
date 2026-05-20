from table_provider.serverside.querystringprocessing import datatablesQueryStringProcessor 

class FilterSet:
    def __init__(self, request, SerializerClass):
        self._filters = []
        self._ordering = []
        self.request = request
        self.SerializerClass = SerializerClass        
        self.field_mappings = SerializerClass.source_mapping()
        self.query_parameters = datatablesQueryStringProcessor(self.request).query_set  
        self.parseFilters()
        self.parseOrdering()
        
    def __iter__(self):
        return iter(self._filters)

    def hasFilters(self):
        return len(self._filters) > 0

    def add_filter(self, filter_requirement):
        self._filters.append(filter_requirement)

    def parseFilters(self):
        
        if 'columns' not in self.query_parameters:
            return
        
        for column in self.query_parameters['columns']:
            data_field = column['data']
            field_type = self.SerializerClass.Meta.datatypes.get(data_field)
            search_value = column['search']['value']

            if not field_type:
                raise ValueError(f"No datatype mapping found for field '{data_field}' in serializer. " + \
                                 "Ensure you have declared all fields that require filtering under datatypes in meta data")

            if search_value:
                if field_type == 'text':
                    filter_req = textFilter(self.field_mappings.get(data_field), search_value)
                elif field_type == 'numeric':                    
                    [filter_min, filter_max ]  = search_value.split('~')
                    if filter_min != "-Inf" or filter_max != "Inf":
                        filter_req = numericRangeFilter(self.field_mappings.get(data_field), filter_min, filter_max)
                    else:
                        continue
                else:
                    continue

                self.add_filter(filter_req)

    def parseOrdering(self):
        if 'order' not in self.query_parameters:
            return
        
        order_array = []
        for order_column in self.query_parameters['order']:
            order_array = []
            column_idx = int(order_column['column'])
            json_name = self.query_parameters['columns'][column_idx]['data']
            db_name = self.field_mappings.get(json_name)
            order_direction = '' if order_column['dir'] == 'asc' else '-'
            order_array.append((f"{order_direction}{db_name}") )
        self._ordering = order_array


    def get_filters(self, data_field=None):
        return self._filters
    
    def get_ordering(self):
        return self._ordering

class filterRequirement:
    def __init__(self, db_field_name, filter_type):
        self.filter_type = filter_type
        self.db_field_name = db_field_name
        self.filter_values = None

class textFilter(filterRequirement):
    def __init__(self, db_field_name, filter_value):
        super().__init__(db_field_name, 'text')

        if "," in filter_value:
            self.filter_values = filter_value.split(',')
            self.filter_action = 'in'
        elif "%" in filter_value:
            self.filter_values = filter_value.replace("%", "")
            self.filter_action = 'contains'
        else:
            self.filter_values = filter_value
            self.filter_action = ''    
    
    def format_django(self):
        if(self.filter_action == 'in'):
            return {f"{self.db_field_name}__in": self.filter_values}
        if(self.filter_action == 'contains'):
            return {f"{self.db_field_name}__contains": self.filter_values}
        else:
            return {f"{self.db_field_name}": self.filter_values}

class numericRangeFilter(filterRequirement):
    def __init__(self, db_field_name, filter_min, filter_max):
        super().__init__(db_field_name, 'numeric')
        if (filter_min == '-Inf' and filter_max == 'Inf'):
            self.filter_values = { 'min': filter_min, 'max': filter_max }
            self.filter_action = 'between'
        if (filter_min != '-Inf' and filter_max != 'Inf'):
            self.filter_values = { 'min': filter_min, 'max': filter_max }
            self.filter_action = 'between'
        elif filter_min != '-Inf':
            self.filter_values = { 'min': filter_min }
            self.filter_action = 'gt'
        elif filter_max != 'Inf':
            self.filter_values = { 'max': filter_max }
            self.filter_action = 'lt'

    def format_django(self):
        if(self.filter_action == 'between'):
            return {f"{self.db_field_name}__gt": self.filter_values.get('min'), 
                    f"{self.db_field_name}__lt": self.filter_values.get('max')}
        elif(self.filter_action == 'gt'):
            return {f"{self.db_field_name}__{self.filter_action}": self.filter_values['min']}
        elif(self.filter_action == 'lt'):
            return {f"{self.db_field_name}__{self.filter_action}": self.filter_values['max']}