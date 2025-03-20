from django.shortcuts import render
from django.http import HttpResponse, HttpResponseBadRequest
from django.conf import settings
from django.views.generic import TemplateView
from django import forms
from protein.models import Protein, ProteinFamily
from common.phylogenetic_tree import PhylogeneticTreeGenerator

import json
from copy import deepcopy
from collections import OrderedDict
import sys


try:
    import importlib.metadata
except ImportError:
    sys.modules['importlib.metadata'] = __import__('importlib_metadata')

import pandas as pd
from sklearn.manifold import TSNE
from sklearn.cluster import KMeans
import matplotlib.colors as mcolors
import re

import openpyxl
import os


class DataMapperHome(TemplateView):

    def dispatch(self, request, *args, **kwargs):
        """Ensure 'page' is always set for both GET and POST requests"""

        # Extract from URL (GET)
        if 'page' in kwargs:
            self.page = kwargs['page']
        
        # Extract from POST (ensure it is there)
        elif request.method == 'POST':
            self.page = request.POST.get('page')

        # If 'page' is still None, return an error
        if not self.page:
            return HttpResponseBadRequest("Missing 'page' parameter")
        
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        """Ensure the correct template is used"""
        return [f'mapper/DataMapperHome{self.page}.html']

    def get_context_data(self, **kwargs):
        """Pass the page variable into the context"""
        context = super().get_context_data(**kwargs)
        context['page'] = self.page  # Pass 'page' to the template
        return context

    @staticmethod
    def keep_by_names(data, names_to_keep):
        data_copy = deepcopy(data)
        if isinstance(data_copy, list):
            # Process each item in the list
            kept_items = [DataMapperHome.keep_by_names(item, names_to_keep) for item in data_copy]
            # Return only non-None items
            return [item for item in kept_items if item is not None]
        elif isinstance(data_copy, OrderedDict):
            name = data_copy.get('name')
            if name not in names_to_keep.keys():
                if 'children' in data_copy:
                    # Recursively process children
                    data_copy['children'] = DataMapperHome.keep_by_names(data_copy['children'], names_to_keep)
                    # Remove the 'children' key if it's empty after processing
                    if not data_copy['children']:
                        return None
                else:
                    return None
            else:
                # If the name is in the keep list, update the 'value' field
                data_copy['value'] = names_to_keep[name]['Inner']
                # Process children if present
                if 'children' in data_copy:
                    data_copy['children'] = DataMapperHome.keep_by_names(data_copy['children'], names_to_keep)
                    if not data_copy['children']:
                        del data_copy['children']
            return data_copy
        return data_copy

    @staticmethod
    def convert_keys(datatree, conversion):
        new_tree = {}
        for key, value in datatree.items():
            # Convert the key using the conversion dictionary
            new_key = conversion.get(key, key)  # Fallback to the original key if no conversion is found
            if isinstance(value, dict):
                # Recursively convert keys of nested dictionaries
                new_tree[new_key] = DataMapperHome.convert_keys(value, conversion)
            else:
                # If the value is a list (end of the branch), just assign it
                new_tree[new_key] = value
        return new_tree

    @staticmethod
    def reassign_keys(original_dict, key_mappings):
         # Create a new dictionary to store the reassigned keys
         new_dict = {}
         # Iterate over the list of tuples (new_key, old_key)
         for new_key, old_key in key_mappings:
             # Check if the old_key exists in the original dictionary
             if old_key in original_dict:
                 # Assign the value from the original dictionary to the new key
                 new_dict[new_key] = original_dict[old_key]

         return new_dict

    @staticmethod
    def filter_and_extend_dict(big_dict, small_dict):
        def filter_dict(d, keys_set):
            filtered_dict = {}
            for key, value in d.items():
                if isinstance(value, dict):
                    filtered_sub_dict = filter_dict(value, keys_set)
                    if filtered_sub_dict:
                        filtered_dict[key] = filtered_sub_dict
                elif isinstance(value, list):
                    filtered_values = [v for v in value if v in keys_set]
                    if filtered_values:
                        filtered_dict[key] = filtered_values
            return filtered_dict

        def extend_dict(d, additional_values):
            for key, value in d.items():
                if isinstance(value, dict):
                    extend_dict(value, additional_values)
                elif isinstance(value, list):
                    extended_list = []
                    for item in value:
                        if item in additional_values:
                            # Wrap values into a list and add an extra dictionary layer
                            extended_list.append({item: [additional_values[item]['Value1'], additional_values[item]['Value2']]})
                        else:
                            extended_list.append(item)
                    d[key] = extended_list

        # Step 1: Filter the big dictionary
        filtered_dict = filter_dict(big_dict, set(small_dict.keys()))

        # Step 2: Extend the filtered dictionary
        extend_dict(filtered_dict, small_dict)

        return filtered_dict

    @staticmethod
    def filter_dict(d, elements):
        filtered_dict = {}
        for key, value in d.items():
            if isinstance(value, dict):
                filtered_sub_dict = DataMapperHome.filter_dict(value, elements)
                if filtered_sub_dict:
                    filtered_dict[key] = filtered_sub_dict
            elif isinstance(value, list):
                filtered_values = [v for v in value if v in elements]
                if filtered_values:
                    filtered_dict[key] = filtered_values
        return filtered_dict

    @staticmethod
    def generate_list_plot(listplot): #ADD AN INPUT FILTER DICTIONARY
        # Generate the master dict of protein families

        data = list(listplot.keys())
        names = list(Protein.objects.filter(entry_name__in=data).values_list('name', flat=True))
        # Names conversion dict
        names_dict = Protein.objects.filter(entry_name__in=data).values('entry_name', 'name').order_by('entry_name')
        names_conversion_dict = {item['entry_name']: item['name'] for item in names_dict}
        IUPHAR_to_uniprot_dict = {item['name']: item['entry_name'] for item in names_dict}

        families = ProteinFamily.objects.all()
        datatree = {}
        conversion = {}
        for item in families:
            if len(item.slug) == 3 and item.slug not in datatree.keys():
                datatree[item.slug] = {}
                conversion[item.slug] = item.name
            if len(item.slug) == 7 and item.slug not in datatree[item.slug[:3]].keys():
                datatree[item.slug[:3]][item.slug[:7]] = {}
                conversion[item.slug] = item.name
            if len(item.slug) == 11 and item.slug not in datatree[item.slug[:3]][item.slug[:7]].keys():
                datatree[item.slug[:3]][item.slug[:7]][item.slug[:11]] = []
                conversion[item.slug] = item.name
            if len(item.slug) == 15 and item.slug not in datatree[item.slug[:3]][item.slug[:7]][item.slug[:11]]:
                datatree[item.slug[:3]][item.slug[:7]][item.slug[:11]].append(item.name)

        datatree2 = DataMapperHome.convert_keys(datatree, conversion)
        datatree2.pop('Parent family', None)
        datatree3 = DataMapperHome.filter_dict(datatree2, names)
        data_converted = {names_conversion_dict[key]: value for key, value in listplot.items()}
        Data_full = {"NameList": datatree3, "DataPoints": data_converted, "LabelConversionDict":IUPHAR_to_uniprot_dict}
        return Data_full

    @staticmethod
    def generate_GPCRome_data(data):
        #Adjust call to exclude odorants
        all_proteins = Protein.objects.filter(species_id=1, parent_id__isnull=True, accession__isnull=False, family_id__slug__startswith='0').exclude(
                                            family_id__slug__startswith='007'
                                        ).exclude(
                                            family_id__slug__startswith='008'
                                        )

        result_dict = {}
        for prot in all_proteins:
            key = prot.entry_name
            # Initialize the key in result_dict if not already present
            if key not in result_dict:
                result_dict[key] = '0'

        for key in data:
            if 'Value1' in data[key]:
                if key in result_dict and bool(data[key]['Value1']):
                    result_dict[key] = data[key]['Value1']

        proteins = list(Protein.objects.filter(entry_name__in=result_dict.keys()
            ).values('entry_name', 'name').order_by('entry_name'))

        names_conversion_dict = {item['entry_name']: item['name'] for item in proteins}

        names = list(names_conversion_dict.values())

        IUPHAR_to_uniprot_dict = {item['name']: item['entry_name'] for item in proteins}

        families = ProteinFamily.objects.all()
        datatree = {}
        conversion = {}

        for item in families:
            if len(item.slug) == 3 and item.slug not in datatree.keys():
                datatree[item.slug] = {}
                conversion[item.slug] = item.name
            if len(item.slug) == 7 and item.slug not in datatree[item.slug[:3]].keys():
                datatree[item.slug[:3]][item.slug[:7]] = {}
                conversion[item.slug] = item.name
            if len(item.slug) == 11 and item.slug not in datatree[item.slug[:3]][item.slug[:7]].keys():
                datatree[item.slug[:3]][item.slug[:7]][item.slug[:11]] = []
                conversion[item.slug] = item.name
            if len(item.slug) == 15 and item.slug not in datatree[item.slug[:3]][item.slug[:7]][item.slug[:11]]:
                datatree[item.slug[:3]][item.slug[:7]][item.slug[:11]].append(item.name)

        datatree2 = DataMapperHome.convert_keys(datatree, conversion)
        datatree2.pop('Parent family', None)
        datatree3 = DataMapperHome.filter_dict(datatree2, names)
        data_converted = {names_conversion_dict[key]: {'Value1':value} for key, value in result_dict.items()}
        data_full = {"NameList": datatree3, "DataPoints": data_converted, "LabelConversionDict":IUPHAR_to_uniprot_dict}

        # Construct Master_dict for GPCRome wheel.
        Master_dict = {}

        for Class in data_full['NameList']:
            Master_dict.setdefault(Class, {})

            for Ligand_type in data_full['NameList'][Class]:
                Master_dict[Class].setdefault(Ligand_type, {})

                for Receptor_Family in data_full['NameList'][Class][Ligand_type]:
                    Master_dict[Class][Ligand_type].setdefault(Receptor_Family, {})

                    for Receptor in data_full['NameList'][Class][Ligand_type][Receptor_Family]:
                        Master_dict[Class][Ligand_type][Receptor_Family].setdefault(Receptor, {})

                        if Receptor in data_full['DataPoints']:
                            receptor_data = data_full['DataPoints'][Receptor]

                            if 'Value1' in receptor_data:
                                Master_dict[Class][Ligand_type][Receptor_Family][Receptor]['Value1'] = receptor_data['Value1']
                            
                            if 'Value2' in receptor_data:
                                Master_dict[Class][Ligand_type][Receptor_Family][Receptor]['Value2'] = receptor_data['Value2']

        # Redistribute the entries from the master_dict into the GPCRome_dict.
        # Initialize GPCRome_dict
        GPCRome_dict = {
            "Circle_1": {},
            "Circle_2": {},
            "Circle_3": {},
            "Circle_4": {},
            "Circle_5": {}
        }

        # Track how many Receptor Families have been added to Circle_1
        class_A_receptor_families = 0

        for Class, ligand_types in Master_dict.items():
            
            # Handle Class A (Rhodopsin) Separately
            if Class == "Class A (Rhodopsin)":
                sorted_receptor_families = []  # Collect receptor families for sorting
                
                for Ligand_type, receptor_families in ligand_types.items():
                    # ** Skip "Orphan receptors" ligand type completely **
                    if Ligand_type == "Orphan receptors":
                        continue  

                    for Receptor_Family in receptor_families:
                        # ** Skip "Class A Orphans" in main processing **
                        if Receptor_Family == "Class A Orphans":
                            continue
                        
                        sorted_receptor_families.append((Ligand_type, Receptor_Family, receptor_families[Receptor_Family]))

                # Sort receptor families alphabetically by Receptor_Family name
                sorted_receptor_families.sort(key=lambda x: x[1])  

                # Process sorted receptor families
                for Ligand_type, Receptor_Family, receptors in sorted_receptor_families:
                    # First 42 go into Circle_1
                    target_circle = "Circle_1" if class_A_receptor_families < 42 else "Circle_2"

                    # Insert data into the target circle using setdefault() to remove redundancy
                    GPCRome_dict.setdefault(target_circle, {}).setdefault(Class, {}).setdefault(Ligand_type, {})[Receptor_Family] = receptors

                    # Increment the count of Class A receptor families
                    class_A_receptor_families += 1

                # Move "Class A Orphans" into Circle_2 **only if not processed already**
                if "Orphan receptors" in ligand_types and "Class A orphans" in ligand_types["Orphan receptors"]:
                    print("bob")
                    GPCRome_dict["Circle_2"].setdefault(Class, {}).setdefault("Orphan receptors", {})["Class A orphans"] = ligand_types["Orphan receptors"]["Class A orphans"]

            # Handle Circle 3: Class B1 (Secretin) and Class B2 (Adhesion)
            elif Class in ["Class B1 (Secretin)", "Class B2 (Adhesion)"]:
                GPCRome_dict["Circle_3"].setdefault(Class, {}).update(ligand_types)

            # Handle Circle 4: Class C (Glutamate)
            elif Class == ["Class C (Glutamate)", "Class F (Frizzled)"]: 
                GPCRome_dict["Circle_4"].setdefault(Class, {}).update(ligand_types)

            # Handle Circle 5: Class F (Frizzled), Class T2 (Taste 2), Other GPCRs
            elif Class in ["Class T2 (Taste 2)", "Other GPCRs"]:
                GPCRome_dict["Circle_5"].setdefault(Class, {}).update(ligand_types)

        # Define a mapping for renaming classes
        class_rename_map = {
            "Class A (Rhodopsin)": "A",
            "Class B1 (Secretin)": "B1",
            "Class B2 (Adhesion)": "B2",
            "Class C (Glutamate)": "C",
            "Class F (Frizzled)": "F",
            "Class T2 (Taste 2)": "T2",
            "Other GPCRs": "Classless"
        }

        # Rename the classes in GPCRome_dict in place
        for circle in GPCRome_dict:
            for old_class_name in list(GPCRome_dict[circle].keys()):
                if old_class_name in class_rename_map:
                    GPCRome_dict[circle][class_rename_map[old_class_name]] = GPCRome_dict[circle].pop(old_class_name)

        # Remove the ligand type from the dictionary
        for circle in GPCRome_dict:
            for class_name in list(GPCRome_dict[circle].keys()):
                new_structure = {}  # Dictionary to hold receptor families directly under the class
                
                for ligand_type in list(GPCRome_dict[circle][class_name].keys()):
                    for receptor_family, receptors in GPCRome_dict[circle][class_name][ligand_type].items():
                        # Merge receptor families under the class directly
                        new_structure[receptor_family] = receptors

                # Replace the old structure with the new one
                GPCRome_dict[circle][class_name] = new_structure

        
        data_full['Master_dict'] = Master_dict
        data_full['GPCRome_dict'] = GPCRome_dict

        return data_full

    @staticmethod
    def generate_tree_plot(input_data): #ADD AN INPUT FILTER DICTIONARY
        ### TREE SECTION
        tree = PhylogeneticTreeGenerator()
        class_a_data = tree.get_tree_data(ProteinFamily.objects.get(name='Class A (Rhodopsin)'))
        class_b1_data = tree.get_tree_data(ProteinFamily.objects.get(name__startswith='Class B1 (Secretin)'))
        class_b2_data = tree.get_tree_data(ProteinFamily.objects.get(name__startswith='Class B2 (Adhesion)'))
        class_c_data = tree.get_tree_data(ProteinFamily.objects.get(name__startswith='Class C (Glutamate)'))
        class_f_data = tree.get_tree_data(ProteinFamily.objects.get(name__startswith='Class F (Frizzled)'))
        class_t2_data = tree.get_tree_data(ProteinFamily.objects.get(name__startswith='Class T2 (Taste 2)'))
        ### GETTING NODES
        data_a = class_a_data.get_nodes_dict(None)
        data_b1 = class_b1_data.get_nodes_dict(None)
        data_b2 = class_b2_data.get_nodes_dict(None)
        data_c = class_c_data.get_nodes_dict(None)
        data_f = class_f_data.get_nodes_dict(None)
        data_t2 = class_t2_data.get_nodes_dict(None)
        #Collating everything into a single tree
        general_options = {'depth': 4,
                           'branch_length': {1: 'Class A (Rhodopsin)',
                                             2: 'Alicarboxylic acid',
                                             3: 'Gonadotrophin-releasing hormone',
                                             4: ''},
                           'branch_trunc': 0,
                           'leaf_offset': 30,
                           'anchor': "tree_plot",
                           'label_free': [],
                           'fontSize': {
                                'class': "15px",
                                'ligandtype': "14px",
                                'receptorfamily': "13px",
                                'receptor': "12px"
                            }}
        master_dict = OrderedDict([('name', ''),
                                   ('value', 3000),
                                   ('color', ''),
                                   ('children',[])])
        class_a_dict = OrderedDict([('name', 'Class A (Rhodopsin)'),
                                   ('value', 0),
                                   ('color', 'Red'),
                                   ('children',data_a['children'])])
        class_b1_dict = OrderedDict([('name', 'Class B1 (Secretin)'),
                                   ('value', 0),
                                   ('color', 'Green'),
                                   ('children',data_b1['children'])])
        class_b2_dict = OrderedDict([('name', 'Class B2 (Adhesion)'),
                                  ('value', 0),
                                  ('color', 'Blue'),
                                  ('children',data_b2['children'])])
        class_c_dict = OrderedDict([('name', 'Class C (Glutamate)'),
                                  ('value', 0),
                                  ('color', 'Purple'),
                                  ('children',data_c['children'])])
        class_f_dict = OrderedDict([('name', 'Class F (Frizzled)'),
                                  ('value', 0),
                                  ('color', 'Grey'),
                                  ('children',data_f['children'])])
        class_t2_dict = OrderedDict([('name', 'Class T2 (Taste 2)'),
                                  ('value', 0),
                                  ('color', 'Orange'),
                                  ('children',data_t2['children'])])
        ### APPENDING TO MASTER DICT
        master_dict['children'].append(class_a_dict)
        master_dict['children'].append(class_b1_dict)
        master_dict['children'].append(class_b2_dict)
        master_dict['children'].append(class_c_dict)
        master_dict['children'].append(class_f_dict)
        master_dict['children'].append(class_t2_dict)

        updated_data = {key.replace('_human', ''): value for key, value in input_data.items()}
        circles = {key.replace('_human', '').upper(): {k: v for k, v in value.items()} for key, value in input_data.items()}
        master_dict = DataMapperHome.keep_by_names(master_dict, updated_data)

        if len(master_dict['children']) == 1:
            master_dict = master_dict['children'][0]
            general_options['depth'] = 3
            general_options['branch_length'] = {1: 'Alicarboxylic acid',
                                             2: 'Gonadotrophin-releasing hormone',
                                             3: ''}
        else:
            pass

        whole_receptors = Protein.objects.prefetch_related("family", "family__parent__parent__parent")
        whole_rec_dict = {}
        for rec in whole_receptors:
            rec_uniprot = rec.entry_short()
            rec_iuphar = rec.family.name.replace("receptor", '').replace("<i>", "").replace("</i>", "").strip()
            if (rec_iuphar[0].isupper()) or (rec_iuphar[0].isdigit()):
                whole_rec_dict[rec_uniprot] = [rec_iuphar]
            else:
                whole_rec_dict[rec_uniprot] = [rec_iuphar.capitalize()]

        return master_dict, general_options, circles, whole_rec_dict

    @staticmethod
    def clustering_test(method, data, data_type):
        # Convert the nested dictionary to a DataFrame
        data = {key.replace('_human', ''): value for key, value in data.items()}
        data_df = pd.DataFrame(data).T

        # Ensure Value1 is always filled with 0 if missing
        if 'Value1' in data_df.columns:
            data_df['Value1'] = data_df['Value1'].fillna(0)

        # Check if Value2 exists in the data
        if 'Value2' in data_df.columns:
            # If some entries have Value2 but others don’t, fill missing ones
            if data_df['Value2'].isnull().sum() > 0:
                # Applying fail-safe.
                # Strategy: Fill missing Value2 with the **mean** of existing ones
                mean_value2 = data_df['Value2'].mean()
                data_df['Value2'] = data_df['Value2'].fillna(mean_value2)

        if 'Value2' in data_df.columns:
            # Example usage
            reduced_df = DataMapperHome.reduce_and_cluster(data_df['Value2'], method=method)
            df_merged = pd.merge(reduced_df, data_df['Value1'], left_on='label', right_index=True, how='left')
            df_merged.rename(columns={'Value1': 'fill'}, inplace=True)

            ## add class/ligand_type/receptor_family clusters ##

            # Step 1: Fetch data
            proteins = Protein.objects.filter(
                parent_id__isnull=True, species_id=1
            ).values_list(
                'entry_name',
                "family__parent__parent__parent__name",  # To be renamed as 'Class'
                'family__parent__parent__name',  # To be renamed as 'Ligand type'
                'family__parent__name'  # To be renamed as 'Receptor family'
            )

            # Step 2: Convert to a DataFrame
            proteins_df = pd.DataFrame(list(proteins), columns=['entry_name', 'Class', 'Ligand type', 'Receptor family'])

            # Step 3: Remove '_human' suffix from 'entry_name'
            proteins_df['entry_name'] = proteins_df['entry_name'].str.replace('_human', '')

            # Step 4: Rename 'entry_name' to 'label'
            proteins_df = proteins_df.rename(columns={'entry_name': 'label'})

            # Step 5: Merge with reduced_df on 'label'
            merged_df = pd.merge(df_merged, proteins_df, on='label', how='left')
            # Prepare the data for visualization
            data_json = merged_df.to_json(orient='records')
        else:
            if data_type == 'seq':
                # Get the info of the plot
                full_matrix = DataMapperHome.generate_full_matrix(method)
                # full_matrix_structure = DataMapperHome.generate_full_matrix_structure(method)

                # Filter the original fill matrix based on what we use provided
                reduced_input = full_matrix[full_matrix['label'].isin(list(data.keys()))]
                data_df = pd.DataFrame(data).T
                # Merge the dataframes
                df_merged = pd.merge(reduced_input, data_df['Value1'], left_on='label', right_index=True, how='left')
                df_merged.rename(columns={'Value1': 'fill'}, inplace=True)
                # Prepare the data for visualization
                data_json = df_merged.to_json(orient='records')
            elif data_type == 'structure':
                # Get the info of the plot
                full_matrix_structure = DataMapperHome.generate_full_matrix_structure(method)

                # Filter the original fill matrix based on what we use provided
                reduced_input = full_matrix_structure[full_matrix_structure['label'].isin(list(data.keys()))]
                data_df = pd.DataFrame(data).T
                # Merge the dataframes
                df_merged = pd.merge(reduced_input, data_df['Value1'], left_on='label', right_index=True, how='left')
                df_merged.rename(columns={'Value1': 'fill'}, inplace=True)
                # Prepare the data for visualization
                data_json = df_merged.to_json(orient='records')

        return data_json

    # Generate full similarity matrix for cluster or load existing #
    def generate_full_matrix(method):
        Data_dir = settings.DATA_DIR
        output_file = os.sep.join([Data_dir, 'structure_data', 'HumanGPCRSimilarityAllData_{}.csv'.format(method)])
        # Check if the file exists
        if os.path.exists(output_file):
            # Load the data from the existing file
            merged_df = pd.read_csv(output_file, index_col=0)
        else:
            # Original processing steps
            similarity_matrix_file = os.sep.join([Data_dir, 'structure_data', 'human_gpcr_similarity_data_all_segments.csv'])
            data = pd.read_csv(similarity_matrix_file)
            data = data[['receptor1_entry_name', 'receptor2_entry_name', 'similarity']]
            matrix = data.pivot(index='receptor1_entry_name', columns='receptor2_entry_name', values='similarity')
            matrix.index = matrix.index.str.replace('_human', '', regex=False)
            matrix.columns = matrix.columns.str.replace('_human', '', regex=False)
            matrix = matrix.fillna(100)

            # ---------------------------------------------
            # Step 2: Normalize Similarity Values to [0, 1]
            # ---------------------------------------------

            normalized_matrix = matrix / 100.0

            distance_matrix_df = 1.0 - normalized_matrix

            # Perform reduction and clustering
            reduced_df = DataMapperHome.reduce_and_cluster(distance_matrix_df, method='tsne')

            reduced_df['label'] = reduced_df['label'].apply(lambda x: x.split('[Human] ')[1] if '[Human] ' in x else x)
            reduced_df['label'] = reduced_df['label'].apply(lambda x: x.split('_human')[0] if '_human' in x else x)

            # add class/ligand_type/receptor_family clusters

            # Step 1: Fetch data
            proteins = Protein.objects.filter(
                parent_id__isnull=True, species_id=1
            ).values_list(
                'entry_name',
                "family__parent__parent__parent__name",  # To be renamed as 'Class'
                'family__parent__parent__name',  # To be renamed as 'Ligand type'
                'family__parent__name'  # To be renamed as 'Receptor family'
            )

            # Step 2: Convert to a DataFrame
            proteins_df = pd.DataFrame(list(proteins), columns=['entry_name', 'Class', 'Ligand type', 'Receptor family'])
            proteins_df.to_excel(os.sep.join([settings.DATA_DIR, 'structure_data', 'All_GPCRs_ligandType_Families.xlsx']),index=False)

            # Step 3: Remove '_human' suffix from 'entry_name'
            proteins_df['entry_name'] = proteins_df['entry_name'].str.replace('_human', '')

            # Step 4: Rename 'entry_name' to 'label'
            proteins_df = proteins_df.rename(columns={'entry_name': 'label'})

            # Step 5: Merge with reduced_df on 'label'
            merged_df = pd.merge(reduced_df, proteins_df, on='label', how='left')

            # Save the reduced DataFrame to a CSV file
            merged_df.to_csv(output_file)

        return merged_df

    @staticmethod
    def reduce_and_cluster(data, method='tsne', n_components=2, n_clusters=5):
        # if method == 'umap':
        #     reducer = umap.UMAP(n_components=n_components, random_state=42)
        if method == 'tsne':
            reducer = TSNE(n_components=n_components, random_state=42)
        # elif method == 'pca':
        #     reducer = PCA(n_components=n_components, random_state=42)
        else:
            raise ValueError("Method should be either 'umap' or 'tsne'")

        reduced_data = reducer.fit_transform(data)

        # Clustering the reduced data
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        clusters = kmeans.fit_predict(reduced_data)

        # Prepare the data for D3.js
        df = pd.DataFrame(reduced_data, columns=['x', 'y'])
        df['cluster'] = clusters
        df['label'] = data.index

        return df

    @staticmethod
    def map_to_quartile(value, quartiles):
        if value <= quartiles[0.25]:
            return 10
        elif value <= quartiles[0.5]:
            return 20
        elif value <= quartiles[0.75]:
            return 30
        else:
            return 40

    @staticmethod
    def Label_conversion_info(data):
        # Get list of keys
        Name_list = list(data.keys())
        # Names conversion dict
        names_dict = Protein.objects.filter(entry_name__in=Name_list).values('entry_name', 'name').order_by('entry_name')
        UniProt_to_IUPHAR_converter = {item['entry_name']: item['name'] for item in names_dict}
        IUPHAR_to_UniProt_converter = {item['name']: item['entry_name'] for item in names_dict}
        Label_converter = {'UniProt_to_IUPHAR_converter':UniProt_to_IUPHAR_converter,'IUPHAR_to_UniProt_converter':IUPHAR_to_UniProt_converter}
        return Label_converter
    

    

    def post(self, request, *args, **kwargs):
        ### This method handles POST requests for form submission ###

        if request.method == 'POST':

            # Utilize ExcelUploadForm class #
            form = ExcelUploadForm(request.POST,request.FILES)

            # If form is valid #
            if form.is_valid():

                # Get cleaned data #
                file = form.cleaned_data['file']

                # Check if file is .xlsx #
                if not file.name.endswith('.xlsx'):
                    return render(request, f'mapper/DataMapperHome{self.page}.html', {'upload_status': 'Failed','Error_message': "The uploaded file is not an .xlsx file."})
                else:
                    try:
                        workbook = openpyxl.load_workbook(filename=file,read_only=False)
                    except:
                        return render(request, f'mapper/DataMapperHome{self.page}.html', {'upload_status': 'Failed','Error_message': "Unable to load excel file, might be corrupted or not inline with the template file."})

                    if workbook:

                        # Fetch protein data for processing 1 (Cluster, List, and Heatmap) #
                        all_proteins = Protein.objects.filter(species_id=1, parent_id__isnull=True, accession__isnull=False, family_id__slug__startswith='0').values_list('entry_name', flat=True).distinct()

                        # Fetch protein data for processing 2 (GPCRome wheel and Tree plot) #
                        Proteins_GPCRomeTree = Protein.objects.filter(
                                species_id=1, 
                                parent_id__isnull=True, 
                                accession__isnull=False, 
                                family_id__slug__startswith='0'
                            ).exclude(
                                family_id__slug__startswith='007'
                            ).exclude(
                                family_id__slug__startswith='008'
                            ).values_list('entry_name', flat=True).distinct()

                        # Load excel file (workbook) and get sheet names #
                        sheet_names = workbook.sheetnames

                        # Sheets and headers #

                        Sheet_pass_check = False
                        valid_sheet_name_list = ['GPCRome wheel - Numeric','GPCRome wheel - Text','Tree - Numeric','Tree - Text','Cluster - Numeric','List - Numeric','List - Text','Heatmap - Numeric']

                        # Figure out if the sheet names match a template file #
                        for sheet_name in sheet_names:
                            if sheet_name in valid_sheet_name_list:
                                Sheet_pass_check = True
                            else:
                                pass

                        if not Sheet_pass_check:
                            # Add addition for the different sheets.
                            return render(request, f'mapper/DataMapperHome{self.page}.html', {'upload_status': 'Failed','Error_message': "The excel file is not structured as the template file. There are incorrect sheet names and data setup."})
                        else:
                            
                            ### Initialize Global values ###
                            # Data passed #
                            Data = {}
                            # Incorrect values for the report #
                            Incorrect_values = {}
                            # plot evaluation value #
                            Plot_parser = 'Failed'
                            # Plot name & Datatype
                            plot_name_global = ""
                            plot_type_global = ""

                            # def is_valid_color(color):
                            #     # Check if it's a named color
                            #     if color.lower() in mcolors.CSS4_COLORS:
                            #         return True
                                
                            #     # Check if it's a valid hex color
                            #     hex_pattern = r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$"
                            #     return bool(re.match(hex_pattern, color))

                            # For each sheet in the workbook #
                            for sheet_name in sheet_names:

                                if sheet_name in valid_sheet_name_list:
                                    Plot_name = sheet_name.split(" - ")[0]
                                    Plot_type = sheet_name.split(" - ")[1]

                                    # Set global plot name and datatype
                                    plot_name_global = Plot_name
                                    plot_type_global = Plot_type
                                    # Initialize worksheet #
                                    worksheet = workbook[sheet_name]
                                    
                                    ##########################
                                    ### GPCRome wheel Plot ###
                                    ##########################
                                    if Plot_name == "GPCRome wheel":

                                        Incorrect_values['GPCRs'] = {}
                                        Incorrect_values['GPCR Value (Column B)'] = {}
                                        empty_sheet = True  # Initialize the flag

                                        # Check if the sheet is empty
                                        for row in worksheet.iter_rows(min_row=2, values_only=True):
                                            # Check if column B (index 1) has any non-empty value
                                            if row[1] not in (None, ""):
                                                empty_sheet = False
                                                break
                                        # If sheet is empty continue and report
                                        if empty_sheet:
                                            print("passed")
                                            pass
                                        else:
                                            # If sheet is not empty then start handling the data
                                            # Iterate through the rows and validate the data
                                            for index, row in enumerate(worksheet.iter_rows(min_row=2, values_only=True), start=2):
                                                # Check the "Receptor (Uniprot)" column for correct values
                                                if row[0] not in Proteins_GPCRomeTree:
                                                    if row[0] in (None, ""):
                                                        pass
                                                    else:
                                                        Incorrect_values['GPCRs'][index] = '"{}" is a invalid entry for the GPCRome wheel plot.'.format(row[0])
                                                else:
                                                    # Check if data row is in data and/or initialize it
                                                    if row[0] not in Data:
                                                        Data[row[0]] = {}
                                                    # Check datatype -> Numeric
                                                    if Plot_type == 'Numeric':
                                                        if row[1] not in (None, ""):
                                                            try:
                                                                float_value = float(row[1])
                                                                Data[row[0]]['Value1'] = float_value
                                                            except ValueError:
                                                                Incorrect_values['GPCR Value (Column B)'][index] = 'Non-numeric Value'
                                                    # Check datatype -> Text
                                                    elif Plot_type == 'Text':
                                                        if row[1] not in (None, ""):
                                                            try:
                                                                Text_value = str(row[1])
                                                                Data[row[0]]['Value1'] = Text_value
                                                            except ValueError:
                                                                Incorrect_values['GPCR Value (Column B)'][index] = 'Corrupted Value, not a string'
                                                    else:
                                                        Incorrect_values['Errors'] = 'Incorrect datatype: Was unable to determine datatype to be either Numeric or text. Template might have been changed to something that the DataMapper can not handle.'

                                        # Check if any values are incorrect #
                                        status = 'Success'

                                        if empty_sheet:
                                            status = 'Empty sheet'
                                        elif Data:
                                            for Error_entries in Incorrect_values:
                                                # Check if there are any assigned index values for this col_idx
                                                if any(Incorrect_values[Error_entries].values()):
                                                    # If any index is assigned, set status to 'Partially_success' and break out of the loop
                                                    status = 'Failed'
                                                    break
                                        else:
                                            status = 'Failed'
                                            
                                        ## Update Plot_parser for GPCRome Wheel
                                        Plot_parser = status
                            
                                    #################
                                    ### Tree plot ###
                                    #################

                                    elif Plot_name == 'Tree':
                                        
                                        Incorrect_values['GPCRs'] = {}
                                        IndexToColumn = ['A','B','C','D','E','F','G']
                                        # Initialize the inccorect column values
                                        for key in IndexToColumn[1:]:
                                            Incorrect_values['GPCR Value (Column {})'.format(key)] = {}
                                        empty_sheet = True  # Initialize the flag
                                        TreeNonEmptyEntryCounter = 0
                                        
                                        # Check if sheet is empty
                                        for row in worksheet.iter_rows(min_row=2, values_only=True):
                                            # Check if any value in columns B (1) to G (6) is not None or empty
                                            if any(cell not in (None, "") for cell in row[1:7]):  # Slice [1:7] to include columns B-G
                                                empty_sheet = False
                                                break
                                        
                                        # If sheet is empty continue and report
                                        if empty_sheet:
                                            pass
                                        else:
                                            # Iterate over rows starting from row 2 (min_row=2)
                                            for row in worksheet.iter_rows(min_row=2, values_only=True):
                                                # Check if column A has a value AND at least one column in B-G has a value
                                                if row[0] not in (None, "") and any(cell not in (None, "") for cell in row[1:7]):
                                                    TreeNonEmptyEntryCounter += 1
                                                
                                                # Stop if we exceed 200 valid entries
                                                if TreeNonEmptyEntryCounter > 200:
                                                    break
                                            
                                            if TreeNonEmptyEntryCounter > 200:
                                                Incorrect_values['Error'] = "Detected more than 200 entries. The Tree can not handle that many GPCRs to be able to visualize them in one plot."
                                            else:
                                                # If sheet is not empty then start handling the data
                                                # Iterate through the rows and validate the data
                                                for index, row in enumerate(worksheet.iter_rows(min_row=2, values_only=True), start=2):
                                                    # Check the "Receptor (Uniprot)" column for correct values
                                                    if row[0] not in Proteins_GPCRomeTree:
                                                        if row[0] in (None, ""):
                                                            pass
                                                        else:
                                                            Incorrect_values['GPCRs'][index] = '"{}" is a invalid entry for the Tree plot.'.format(row[0])
                                                    else:
                                                        # Check if data row is in data and/or initialize it
                                                        if row[0] not in Data:
                                                            Data[row[0]] = {}
                                                        # Check datatype -> Numeric or Text:
                                                        if Plot_type in ('Numeric','Text'):
                                                            for i in range(1,7):
                                                                # Check datatype -> Numeric
                                                                if Plot_type == 'Numeric':
                                                                    if row[i] not in (None, ""):
                                                                        try:
                                                                            float_value = float(row[i])
                                                                            if i == 1:
                                                                                Data[row[0]]['Inner'] = float_value
                                                                            else:
                                                                                Data[row[0]]['Outer{}'.format(i-1)] = float_value
                                                                        except ValueError:
                                                                            Incorrect_values['GPCR Value (Column {})'.format(IndexToColumn[i])][index] = 'Non-numeric Value'
                                                                # Check datatype -> Text
                                                                elif Plot_type == 'Text':
                                                                    if row[i] not in (None, ""):
                                                                        try:
                                                                            Text_value = str(row[i])
                                                                            Data[row[0]]['Value{}'.format(i)] = Text_value
                                                                        except ValueError:
                                                                            Incorrect_values['GPCR Value (Column {})'.format(IndexToColumn[i])][index] = 'Corrupted Value, not a string'
                                                        else:
                                                            Incorrect_values['Errors'] = 'Incorrect datatype: Was unable to determine datatype to be either Numeric or text. Template might have been changed to something that the DataMapper can not handle.'
                                                # Check if any values are incorrect #
                                                status = 'Success'

                                                if empty_sheet:
                                                    status = 'Empty sheet'
                                                elif Data:
                                                    for Error_entries in Incorrect_values:
                                                        # Check if there are any assigned index values for this col_idx
                                                        if any(Incorrect_values[Error_entries].values()):
                                                            # If any index is assigned, set status to 'Partially_success' and break out of the loop
                                                            status = 'Failed'
                                                            break
                                                else:
                                                    status = 'Failed'
                                                    
                                                ## Update Plot_parser for GPCRome Wheel
                                                Plot_parser = status
                                    
                                    ####################
                                    ### Cluster plot ###
                                    ####################

                                    elif Plot_name == 'Cluster':

                                        Incorrect_values['GPCRs'] = {}
                                        Incorrect_values['GPCR Value (Column B)'] = {}
                                        Incorrect_values['GPCR Spacial position (Column C)'] = {}
                                        Incorrect_values['GPCR Value (Column B & C)'] = {}
                                        ClusterSpacialPositionCheck = False
                                        empty_sheet = True  # Initialize the flag
                                        
                                        # Check if the sheet is empty
                                        for row in worksheet.iter_rows(min_row=2, values_only=True):
                                            # Check if any value in columns B (1) and C (2) is not None or empty
                                            if any(cell not in (None, "") for cell in (row[1], row[2])):  # Only check B and C
                                                empty_sheet = False
                                                break

                                        # If sheet is empty continue and report
                                        if empty_sheet:
                                            pass
                                        else:
                                            
                                            # Iterate over rows starting from row 2
                                            for row in worksheet.iter_rows(min_row=2, values_only=True):
                                                # Check if both column A (0) and column C (2) have values
                                                if row[0] not in (None, "") and row[2] not in (None, ""):
                                                    ClusterSpacialPositionCheck = True
                                                    break  # Stop checking as soon as we find a valid entry

                                            # If sheet is not empty then start handling the data
                                            # Iterate through the rows and validate the data
                                            for index, row in enumerate(worksheet.iter_rows(min_row=2, values_only=True), start=2):
                                                # Check the "Receptor (Uniprot)" column for correct values
                                                if row[0] not in all_proteins:
                                                    if row[0] in (None, ""):
                                                        pass
                                                    else:
                                                        Incorrect_values['GPCRs'][index] = '"{}" is a invalid entry for the Cluster plot.'.format(row[0])
                                                else:
                                                    # Check if data row is in data and/or initialize it
                                                    if row[0] not in Data:
                                                        Data[row[0]] = {}
                                                    if ClusterSpacialPositionCheck:
                                                        # Check datatype -> Numeric
                                                        if Plot_type == 'Numeric':
                                                            if row[1] not in (None, ""):
                                                                try:
                                                                    float_value = float(row[1])
                                                                    Data[row[0]]['Value1'] = float_value
                                                                except ValueError:
                                                                    Incorrect_values['GPCR Value (Column B)'][index] = 'Non-numeric Value.'
                                                                try:
                                                                    float_value = float(row[2])
                                                                    Data[row[0]]['Value2'] = float_value
                                                                except ValueError:
                                                                    Incorrect_values['GPCR Spacial position (Column C)'][index] = 'Non-numeric Value.'
                                                            else:
                                                                if row[2] not in (None, ""):
                                                                    Incorrect_values['GPCR Value (Column B & C)'][index] = 'You have Spacial position (Column C) without a value assign (Column B), Please assign a value to this row in Column B.'
                                                                else:
                                                                    pass
                                                        else:
                                                            Incorrect_values['Errors'] = 'Incorrect datatype: Was unable to determine datatype to be Numeric. Template might have been changed to something that the DataMapper can not handle.'
                                                    else:
                                                        # Check datatype -> Numeric
                                                        if Plot_type == 'Numeric':
                                                            if row[1] not in (None, ""):
                                                                try:
                                                                    float_value = float(row[1])
                                                                    Data[row[0]]['Value1'] = float_value
                                                                except ValueError:
                                                                    Incorrect_values['GPCR Value (Column B)'][index] = 'Non-numeric Value.'
                                                        else:
                                                            Incorrect_values['Errors'] = 'Incorrect datatype: Was unable to determine datatype to be Numeric. Template might have been changed to something that the DataMapper can not handle.'

                                        # Check if any values are incorrect #
                                        status = 'Success'

                                        if empty_sheet:
                                            status = 'Empty sheet'
                                        elif Data:
                                            for Error_entries in Incorrect_values:
                                                # Check if there are any assigned index values for this col_idx
                                                if any(Incorrect_values[Error_entries].values()):
                                                    # If any index is assigned, set status to 'Partially_success' and break out of the loop
                                                    status = 'Failed'
                                                    break
                                        else:
                                            status = 'Failed'
                                            
                                        ## Update Plot_parser for GPCRome Wheel
                                        Plot_parser = status


                                    #################
                                    ### List plot ###
                                    #################

                                    elif Plot_name == 'List':

                                        Incorrect_values['GPCRs'] = {}
                                        IndexToColumn = ['A','B','C','D','E','F','G',"H","I"]
                                        # Initialize the inccorect column values
                                        for key in IndexToColumn[1:]:
                                            Incorrect_values['GPCR Value (Column {})'.format(key)] = {}
                                        empty_sheet = True  # Initialize the flag
                                        
                                        # Check if sheet is empty
                                        for row in worksheet.iter_rows(min_row=2, values_only=True):
                                            # Check if any value in columns B (1) to G (6) is not None or empty
                                            if any(cell not in (None, "") for cell in row[1:7]):  # Slice [1:7] to include columns B-G
                                                empty_sheet = False
                                                break
                                        
                                        # If sheet is empty continue and report
                                        if empty_sheet:
                                            pass
                                        else:
                                            # If sheet is not empty then start handling the data
                                            # Iterate through the rows and validate the data
                                            for index, row in enumerate(worksheet.iter_rows(min_row=2, values_only=True), start=2):
                                                # Check the "Receptor (Uniprot)" column for correct values
                                                if row[0] not in all_proteins:
                                                    if row[0] in (None, ""):
                                                        pass
                                                    else:
                                                        Incorrect_values['GPCRs'][index] = '"{}" is a invalid entry for the List plot.'.format(row[0])
                                                else:
                                                    # Check if data row is in data and/or initialize it
                                                    if row[0] not in Data:
                                                        Data[row[0]] = {}
                                                    # Check datatype -> Numeric or Text:
                                                    if Plot_type in ('Numeric','Text'):
                                                        # Handle value checks
                                                        for i in range(1,5):
                                                            # Check datatype -> Numeric
                                                            if Plot_type == 'Numeric':
                                                                if row[i] not in (None, ""):
                                                                    try:
                                                                        float_value = float(row[i])
                                                                        Data[row[0]]['Value{}'.format(i)] = float_value
                                                                    except ValueError:
                                                                        Incorrect_values['GPCR Value (Column {})'.format(IndexToColumn[i])][index] = 'Non-numeric Value'
                                                            # Check datatype -> Text
                                                            elif Plot_type == 'Text':
                                                                if row[i] not in (None, ""):
                                                                    try:
                                                                        Text_value = str(row[i])
                                                                        Data[row[0]]['Value{}'.format(i)] = Text_value
                                                                    except ValueError:
                                                                        Incorrect_values['GPCR Value (Column {})'.format(IndexToColumn[i])][index] = 'Corrupted Value, not a string'
                                                        # Handle shapes
                                                        for i in range(5,9):
                                                            if row[i] not in (None, ""):
                                                                if row[i] in ('Circle', 'Diamond', 'Rectangle', 'Star', 'Triangle'):
                                                                    Text_value = str(row[i])
                                                                    Data[row[0]]['Value{}'.format(i)] = Text_value
                                                                else:
                                                                    Incorrect_values['GPCR Value (Column {})'.format(IndexToColumn[i])][index] = 'Value assigned is not empty, Circle, Diamond, Rectangle, Star, or Triangle.'
                                                            else:
                                                                if row[i-4] not in (None, ""):  # Check columns B (1) to E (4)
                                                                    Data[row[0]]['Value{}'.format(i)] = 'Circle'

                                                    else:
                                                        Incorrect_values['Errors'] = 'Incorrect datatype: Was unable to determine datatype to be either Numeric or text. Template might have been changed to something that the DataMapper can not handle.'
                                            # Check if any values are incorrect #
                                            status = 'Success'

                                            if empty_sheet:
                                                status = 'Empty sheet'
                                            elif Data:
                                                for Error_entries in Incorrect_values:
                                                    # Check if there are any assigned index values for this col_idx
                                                    if any(Incorrect_values[Error_entries].values()):
                                                        # If any index is assigned, set status to 'Partially_success' and break out of the loop
                                                        status = 'Failed'
                                                        break
                                            else:
                                                status = 'Failed'
                                                
                                            ## Update Plot_parser for GPCRome Wheel
                                            Plot_parser = status

                               
                                    ###############
                                    ### Heatmap ###
                                    ###############

                                    elif Plot_name == 'Heatmap':
                                        
                                        ## Initialize Local values ##
                                        Incorrect_values['GPCRs'] = {}
                                        IndexToColumn = ['A','B','C','D','E','F']
                                        # Initialize the inccorect column values
                                        for key in IndexToColumn[1:]:
                                            Incorrect_values['GPCR Value (Column {})'.format(key)] = {}
                                        empty_sheet = True  # Initialize the flag
                                        HeatmapNonEmptyEntryCounter = 0
                                        
                                        # Check if sheet is empty
                                        for row in worksheet.iter_rows(min_row=2, values_only=True):
                                            # Check if any value in columns B (1) to G (6) is not None or empty
                                            if any(cell not in (None, "") for cell in row[1:6]):  # Slice [1:6] to include columns B-F
                                                empty_sheet = False
                                                break
                                        
                                        # If sheet is empty continue and report
                                        if empty_sheet:
                                            pass
                                        else:
                                            # Iterate over rows starting from row 2 (min_row=2)
                                            for row in worksheet.iter_rows(min_row=2, values_only=True):
                                                # Check if column A has a value AND at least one column in B-G has a value
                                                if row[0] not in (None, "") and any(cell not in (None, "") for cell in row[1:7]):
                                                    HeatmapNonEmptyEntryCounter += 1
                                                
                                                # Stop if we exceed 200 valid entries
                                                if HeatmapNonEmptyEntryCounter > 50:
                                                    break
                                            
                                            if HeatmapNonEmptyEntryCounter > 50:
                                                Incorrect_values['Error'] = "Detected more than 50 entries. The Heatmap can not handle that many GPCRs to be able to visualize them in one plot."
                                            else:
                                                # If sheet is not empty then start handling the data
                                                # Iterate through the rows and validate the data
                                                for index, row in enumerate(worksheet.iter_rows(min_row=2, values_only=True), start=2):
                                                    # Check the "Receptor (Uniprot)" column for correct values
                                                    if row[0] not in all_proteins:
                                                        if row[0] in (None, ""):
                                                            pass
                                                        else:
                                                            Incorrect_values['GPCRs'][index] = '"{}" is a invalid entry for the Heatmap plot.'.format(row[0])
                                                    else:
                                                        # Check if data row is in data and/or initialize it
                                                        if row[0] not in Data:
                                                            Data[row[0]] = {}
                                                        # Check datatype -> Numeric or Text:
                                                        if Plot_type in ('Numeric','Text'):
                                                            for i in range(1,6):
                                                                # Check datatype -> Numeric
                                                                if Plot_type == 'Numeric':
                                                                    if row[i] not in (None, ""):
                                                                        try:
                                                                            float_value = float(row[i])
                                                                            Data[row[0]]['Value{}'.format(i)] = float_value
                                                                        except ValueError:
                                                                            Incorrect_values['GPCR Value (Column {})'.format(IndexToColumn[i])][index] = 'Non-numeric Value'
                                                        else:
                                                            Incorrect_values['Errors'] = 'Incorrect datatype: Was unable to determine datatype to be either Numeric or text. Template might have been changed to something that the DataMapper can not handle.'
                                                # Check if any values are incorrect #
                                                status = 'Success'

                                                if empty_sheet:
                                                    status = 'Empty sheet'
                                                elif Data:
                                                    for Error_entries in Incorrect_values:
                                                        # Check if there are any assigned index values for this col_idx
                                                        if any(Incorrect_values[Error_entries].values()):
                                                            # If any index is assigned, set status to 'Partially_success' and break out of the loop
                                                            status = 'Failed'
                                                            break
                                                else:
                                                    status = 'Failed'
                                                    
                                                ## Update Plot_parser for GPCRome Wheel
                                                Plot_parser = status
                            
                            #######################################################
                            ## Evaluate the uploaded data and pass on the report ##
                            #######################################################

                            plot_data_json = json.dumps(Data) if Data else "No Data"

                            if Plot_parser in ('Success','Empty sheet'):
                                context = {'upload_status': 'Success',
                                        'Plot_parser': Plot_parser,
                                        'plot_name': plot_name_global,
                                        'plot_type': plot_type_global,
                                        'Data': plot_data_json}
                                if plot_type_global == 'Text' and plot_name_global == 'GPCRome wheel':
                                    print("bob")
                            else:
                                context = {'upload_status': 'Success',
                                        'Plot_parser': Plot_parser,
                                        'plot_name': plot_name_global,
                                        'plot_type': plot_type_global,
                                        'Data': plot_data_json}
                                if Incorrect_values:
                                    context['Incorrect_data_json'] = Incorrect_values
                                else:
                                    context['Incorrect_data_json'] = "No incorrect data"
                            
                            # Return the rendered results
                            return render(request, f'mapper/DataMapperHome{self.page}.html', context)

                    else:
                        return render(request, f'mapper/DataMapperHome{self.page}.html', {'upload_status': 'Failed','Error_message': "Unable to load excel file, might be corrupted or not inline with a template file."})

            else:
                # Return a 405 Method Not Allowed response if not a POST request
                return render(request, f'mapper/DataMapperHome{self.page}.html', {'upload_status': 'Failed','Error_message': "Not a valid excel file. Please try and use the template excel file."})

#######################
## Excel upload form ##
#######################

class ExcelUploadForm(forms.Form):
    file = forms.FileField()

class plotrender(TemplateView):
    template_name = 'mapper/data_mapper_plotrender.html'

    def post(self, request, *args, **kwargs):
        # Retrieve the sample data from the POST request
        Plot_name = request.POST.get('Plot')
        Plot_type_request = request.POST.get('Datatype')
        Data_json = request.POST.get('Data')
        # If Plot_evaluation_json is not None, parse it as JSON
        if Plot_name and Data_json:
            try:
                Plot = Plot_name
                Data = json.loads(Data_json)
                Plot_type = Plot_type_request
            except json.JSONDecodeError:
                # Handle the case when the JSON data is invalid
                return HttpResponse("Invalid JSON data")
            # Contruct context
            context = {'Plot': Plot, 'PlotType': Plot_type}
            
            if Plot:
                 # GPCRome #
                if Plot == 'GPCRome wheel':
                    print("GPCRome success")
                    GPCRome_data = DataMapperHome.generate_GPCRome_data(Data)
                    context['GPCRome_data'] = json.dumps(GPCRome_data["NameList"])
                    context['GPCRome_data_variables'] = json.dumps(GPCRome_data['DataPoints'])
                    context['GPCRome_Label_Conversion'] = json.dumps(GPCRome_data['LabelConversionDict'])
                    context['GPCRome_MasterDict'] = json.dumps(GPCRome_data['Master_dict'])
                    context['GPCRome_WheelDict'] = json.dumps(GPCRome_data['GPCRome_dict'])
                # tree #
                if Plot == 'Tree':
                    print("Tree success")
                    tree, tree_options, circles, receptors = DataMapperHome.generate_tree_plot(Data)
                    context['tree'] = json.dumps(tree)
                    context['tree_options'] = tree_options
                    context['circles'] = json.dumps(circles)
                    context['whole_dict'] = json.dumps(receptors)

                # Cluster analysis #
                if Plot == 'Cluster':
                    print("Cluster success")
                    output_seq = DataMapperHome.clustering_test('tsne', Data,'seq')
                    # output_structure = DataMapperHome.clustering_test('umap', Data['Cluster'],'structure')
                    context['cluster_data_seq'] = output_seq
                    # context['cluster_data_structure'] = output_structure
                    context['plot_type'] = 'Tsne'

                # List plot #
                if Plot == 'List':
                    print("List success")
                    listplot_data = DataMapperHome.generate_list_plot(Data)
                    context['listplot_data'] = json.dumps(listplot_data["NameList"])
                    context['listplot_data_variables'] = json.dumps(listplot_data['DataPoints'])
                    context['Label_Conversion'] = json.dumps(listplot_data['LabelConversionDict'])
                    # context['listplot_datatypes'] = json.dumps(Data['Datatypes']['Listplot'])

                # Heatmap #
                if Plot == 'Heatmap':
                    print("Heatmap success")
                    label_converter = DataMapperHome.Label_conversion_info(Data)
                    context['Label_converter'] = json.dumps(label_converter)
                    context['heatmap_data'] = json.dumps(Data)

            # Return the context dictionary
            return self.render_to_response(context)
        else:
            # Handle the case when Plot_evaluation_json is None
            # This could happen if the form was submitted without the JSON data
            return HttpResponse("Missing sample data")
