#from django.db import connection
#from django.db import IntegrityError
from django.db.models import Q, Count
from django.utils.text import slugify
from django.db import transaction, IntegrityError

from ligand.models import Ligand, LigandID, LigandType, LigandRole
from common.models import WebResource
from common.tools import get_or_create_url_cache, fetch_from_web_api, save_to_cache
from collections import defaultdict, Counter

import time
import os
import re
import requests
import xmltodict

import datamol as dm
import pubchempy as pcp
from pubchempy import BadRequestError, PubChemHTTPError
from rdkit import RDLogger
from rdkit import Chem
from chembl_structure_pipeline import standardizer
from typing import Dict, Any, Optional

# Disable the RDkit verbosity
RDLogger.DisableLog('rdApp.*')

external_sources = ["pubchem", "gtoplig", "chembl_ligand", "drugbank", "drug_central"]

def get_or_create_ligand(name, ids = {}, lig_type = "small-molecule", unichem = False, extended_matching = True, source = None, helm = None):
    """ This function tries to obtain a small molecule Ligand object.

        If the ligand already exists it will return the corresponding object. If
        not, it will process the provided data and create the ligand object.
        When a ligand does not exist, or cannot be created, with the given input
        it will return None

        Parameters
        ----------
        name : str
            Name of the ligand
        ids : dict, optional
            Dictionary where the key is the id_type and the value is the id
            <id_type> is e.g. pubchem, gtp, chembl, etc. (slug of the web_resource)
            <id> is the Identifier itself
        lig_type : str, optional
            String indicating the ligand type (according to the LigandType slugs)
            By default this is set to "small-molecule".
        unichem : bool, optional
            Boolean indicating whether or not to match the compound to other
            sources via UniChem using the GtP ID. By default this is disabled.
        extended_matching : bool, optional
            Boolean indicating whether or not to match the compound
            sources via UniChem using the GtP ID. By default this is enabled.

        Returns
        -------
        obj
            Ligand object or None

        Raises
        ------
        ...Error
            If no ...
    """

    ligand = None
    cas_to_cid_url =  "http://www.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pccompound&retmax=100&term=$index"
    cas_cache_dir = ["CAS", 'cas_codes']

    ### Implementing the Parent structure organization
    # Order of checks:
    ## Check if Standardized SMILES exists
    ## Check if first section of INCHIKEY exists
    ## Check if name exists
    ## if all above fails, generate a parent

    # Check and filter IDs
    for type_id in list(ids.keys()):
        if ids[type_id] is None or ids[type_id] == "None" or ids[type_id] == "":
            del ids[type_id]
        elif isinstance(ids[type_id], str) and ids[type_id].isnumeric():
            ids[type_id] = int(ids[type_id])
        elif isinstance(ids[type_id], str) and is_float(ids[type_id]):
            ids[type_id] = int(float(ids[type_id]))
        elif isinstance(ids[type_id], str):
            ids[type_id] = ids[type_id].strip()
            if type_id == "chembl_ligand":
                ids[type_id] = ids[type_id].upper()
            if type_id == "CAS":
                data = fetch_from_web_api(cas_to_cid_url, ids[type_id], cas_cache_dir, xml=True)
                if data:
                    try:
                        ids["pubchem"] = int(data[3][0].text)
                    except:
                        pass
                del ids["CAS"]
        elif isinstance(ids[type_id], list) and len(ids[type_id]) == 1:
            ids[type_id] = ids[type_id][0]

    # Identify the parent and or create one
    parent = None

    # Attempt using SMILES if available
    if "smiles" in ids:
        std_smiles = standardize_smiles(ids["smiles"])
        if std_smiles:
            parent = try_get_parent({"smiles":std_smiles, "parent__isnull":True})

    # Attempt using InChIKey if parent not yet found
    if not parent and "inchikey" in ids:
        head_inchi = ids["inchikey"].split('-')[0]
        parent = try_get_parent({"clean_inchikey":head_inchi, "parent__isnull":True})

    # # Attempt using sequence if still not found
    # if not parent and "sequence" in ids:
    #     parent = try_get_parent({"sequence":ids["sequence"], "parent__isnull":True})

    # Attempt using name if still not found (here need to add an exception)
    # Here the logic is to find parents which have only the name stored and no other info
    if not parent and "smiles" in ids and "inchikey" in ids:
        std_smiles = standardize_smiles(ids["smiles"])
        head_inchi = ids["inchikey"].split('-')[0]

        if std_smiles:
            new_name = check_name(std_smiles, head_inchi, name)
            if name != new_name:
                # only change the name and skip parent lookup this round
                name = new_name
                # (you can `continue` here if this is in a loop)
                # or just return/exit this branch
                return

        # either std_smiles was falsy, or it was truthy but name==new_name
        parent = try_get_parent({"name__iexact": name, "parent__isnull": True})

    # Final fallback: use name-only matching (case-insensitive)
    if not parent:
        parent = try_get_parent({"name__iexact": name, "parent__isnull": True})

    if not parent:
        for type in external_sources:
            if ligand is None and type in ids:
                ligand = get_ligand_by_id(type, ids[type])
        if ligand:
            if ligand.parent:
                parent = ligand.parent
            else:
                parent = ligand

    # Finally, generate a parent if none was found
    if not parent:
        parent = generate_parent(name, ids, lig_type)

    # No IDs are provided, so the only way forward is a name match
    # Very short name = not unique - minimum is length of 3
    # TODO - add filter for numerical names and typical cpd X names
    # adding the clause 'parent__isnull = False' to all queries since we need to find Ligands, not parents
    if len(ids) == 0:
        results = Ligand.objects.filter(name=name, ambiguous_alias = True, parent__isnull = False)
        if results.count() == 1:
            ligand = results.first()
        # DEBUGGING
        elif results.count() > 1:
            print("Ambiguous name (", name,") as it has ", results.count(), " corresponding entries")
        else:
            # Longer names could be non-ambiguous compounds
            results = Ligand.objects.filter(name__iexact=name, ambiguous_alias = True, parent__isnull = False)
            if results.count() == 1:
                ligand = results.first()
            elif len(name) >= 5:
                results = Ligand.objects.filter(name__iexact=name, ambiguous_alias = False, parent__isnull = False)
                if results.count() == 1:
                    ligand = results.first()
                    # DEBUGGING
                    print("Semi-ambiguous matching using name")
                elif results.count() > 1:
                    print("Error for molecule with name (", name,") as it has ", results.count(), " corresponding entries")

            if ligand is None:
                print("No ligand found with name ",name)
                ligand = create_ligand_from_id(name, "", "", lig_type)
                ligand.ambiguous_alias = True
                if parent and (ligand.pk is None or ligand.pk != parent.pk):
                    ligand.parent = parent
                if source:
                    ligand.source = source
                if helm:
                    ligand.helm = helm
                ligand.save()
                return ligand
    else:
        # Try to find ligand via PubChem ID, Guide to Pharmacology ID, ChEMBL ID
        for type in external_sources:
            if ligand is None and type in ids:
                ligand = get_ligand_by_id(type, ids[type])

        # How about the InChiKey?
        if ligand is None and "inchikey" in ids:
            ligand = get_ligand_by_inchikey(ids["inchikey"])
        elif ligand is None and "smiles" in ids:
            # calculate inchikey from given SMILES and repeat inchikey check
            input_mol = dm.to_mol(ids["smiles"], sanitize=False)
            ligand = get_ligand_by_inchikey(dm.to_inchikey(input_mol))
            # Try again using the InChiKey from the "cleaned" molecule
            if ligand is None:
                ligand = get_ligand_by_inchikey(get_cleaned_inchikey(ids["smiles"]))

        #DEPRECATING UNICHEM SINCE URL HAS CHANGED (FORCING THE INCHI CHECK SINCE THAT STILL WORKS)
        # Tried direct ID matching options => no ligand found => try UniChem IDs before creating new ligand
        if extended_matching and ligand is None:
            external_ids = list(set.intersection(set(ids.keys()), set(external_sources)))
            current_ids = list(ids.values())
            fetch_type = "inchikey"
            if ligand is None and fetch_type in ids:
                unichem_ids = match_id_via_unichem(fetch_type, ids[fetch_type])
                for row in unichem_ids:
                    if row["id"] not in current_ids:
                        ligand = get_ligand_by_id(row["type"], row["id"])
                        current_ids.append(row["id"])
                        if ligand is not None:
                            print("MATCHING", fetch_type, ids[fetch_type], "via UniChem")
                            break

        # Peptide or protein entry Sequence - filter gtoplig as those entries are standalone and should not be merged
        if ligand is None and "sequence" in ids and len(ids["sequence"]) > 3 and "gtoplig" not in ids:
            result = Ligand.objects.filter(sequence = ids["sequence"], parent__isnull = False)
            if result.count() > 0:
                ligand = result.first()
                # DEBUGGING
                if result.count() > 1:
                    print("Ambiguous sequence (", ids["sequence"],") for", name, "as it has ", result.count(), " corresponding entries")

        # UniProt ID if there's no sequence or other IDs
        # TODO figure out best way of matching when sequence and UniProt ID are mixed as there can be multiple variants
        elif ligand is None and "sequence" not in ids and "uniprot" in ids and len(set.intersection(set(ids.keys()), set(external_sources)))==0:
            result = Ligand.objects.filter(uniprot__contains = ids["uniprot"].upper(), parent__isnull = False)
            if result.count() > 0:
                ligand = result.first()
                # DEBUGGING
                if result.count() > 1:
                    print("Ambiguous match - uniprot (", ids["uniprot"],") as it has ", result.count(), " corresponding entries")


        # If the ligand has not been found => create ligand using the provided IDs
        # TODO merge this into one function
        if ligand is None:
            # Creation of peptides and proteins
            if lig_type != "small-molecule" and "sequence" in ids:
                ligand = create_ligand_from_id(name, "sequence", ids["sequence"], lig_type)
                if (ligand is not None) and helm:
                    ligand.helm = helm


            # Creation of small molecules and others without sequence/UniProt
            if ligand is None:
                for type in ["smiles", "pubchem", "gtoplig", "chembl_ligand"]:
                    if type in ids:
                        ligand = create_ligand_from_id(name, type, ids[type], lig_type)
                        if ligand is not None:
                            break

            # Create empty ligand
            if ligand is None:
                tmp_types = list(ids.keys())
                if "uniprot" in tmp_types:
                    tmp_types.remove("uniprot")

                if len(tmp_types) == 0 and len(name) >= 4:
                    # Try to find ligand based on name
                    results = Ligand.objects.filter(name=name, parent__isnull = False, ambiguous_alias = True)
                    if results.count() == 1:
                        ligand = results.first()
                    # DEBUGGING
                    elif results.count() > 1:
                        print("Ambiguous name (", name,") as it has ", results.count(), " corresponding entries")
                    else:
                        results = Ligand.objects.filter(name__iexact=name, parent__isnull = False, ambiguous_alias = True)
                        if results.count() == 1:
                            ligand = results.first()

                if ligand is None:
                    print("Creating an empty ligand", name, ids)
                    ligand = create_ligand_from_id(name, "", "", lig_type)
                    if parent and (ligand.pk is None or ligand.pk != parent.pk):
                        ligand.parent = parent
                    if helm:
                        ligand.helm = helm
                    ligand.ambiguous_alias = True

        # Add missing IDs via (web)links to the ligand object
        if ligand is not None:
            # Validate if newly found inchikey really does not yet exist
            if "inchikey" not in ids and ligand.inchikey is not None and ligand.pk is None:
                test = get_ligand_by_inchikey(ligand.inchikey)
                if test is not None:
                    ligand = test

            # Add provided entries to ligand when missing
            if "pdb" in ids and ligand.pdbe is None:
                ligand.pdbe = ids["pdb"]
            if "uniprot" in ids and ligand.uniprot is None:
                ligand.uniprot = ids["uniprot"].upper()
            if "sequence" in ids and ligand.sequence is None and len(ids["sequence"]) < 1000:
                ligand.sequence = ids["sequence"]
            if "inchikey" in ids and ligand.inchikey is None:
                ligand.inchikey = ids["inchikey"]
            if "smiles" in ids and ligand.smiles is None:
                ligand.smiles = ids["smiles"]
            if parent and (ligand.pk is None or ligand.pk != parent.pk):
                ligand.parent = parent
            if source:
                ligand.source = source
            if helm:
                ligand.helm = helm
            ligand.save()

            # Create list of existing weblinks
            current_ids = []
            for wl in ligand.ids.all():
                current_ids.append(str(wl.index))

            for type_id in ids:
                # If the ID does not yet exist => add
                if ids[type_id] not in current_ids and type_id in external_sources:
                    wr = WebResource.objects.get(slug=type_id)
                    wl, created = LigandID.objects.get_or_create(ligand=ligand, index=ids[type_id], web_resource=wr)
                    #ligand.ids.add(wl)
                    current_ids.append(str(ids[type_id]))

    # Updating the parent data if the child has more data
    if ligand and parent and ligand.pk != parent.pk:
        update_parent(parent, ligand)

    return ligand

unichem_src_types = {"1": "chembl_ligand", "2": "drugbank", "3": "pdb", "4": "gtoplig", "22": "pubchem", "34": "drug_central"}
unichem_src_types_inv = {v: k for k, v in unichem_src_types.items()}

def match_id_via_unichem(type, id):
    results = []
    cache_dir = ['unichem', 'id_match']
    if type in unichem_src_types_inv or type == "pdb":
        type_id = 3 # default to PDB otherwise in list
        if type in unichem_src_types_inv:
            type_id = unichem_src_types_inv[type]
        unichem_url = "https://www.ebi.ac.uk/unichem/rest/src_compound_id/$index/" + type_id
        cache_dir[1] = "id_match_" + type
        unichem = fetch_from_web_api(unichem_url, id, cache_dir)
        if unichem and "error" not in unichem:
            for entry in unichem:
                if entry["src_id"] in unichem_src_types.keys():
                    results.append({"type" : unichem_src_types[entry["src_id"]], "id": entry["src_compound_id"]})
    elif type == "inchikey":
        unichem_url = "https://www.ebi.ac.uk/unichem/rest/inchikey/$index"
        cache_dir[1] = "id_match_" + type
        unichem = fetch_from_web_api(unichem_url, id, cache_dir)
        if unichem and "error" not in unichem:
            for entry in unichem:
                if entry["src_id"] in unichem_src_types.keys():
                    results.append({"type" : unichem_src_types[entry["src_id"]], "id": entry["src_compound_id"]})
    return results


def get_ligand_by_id(type, id, uniprot = None, forced=True):
    if forced:
        if uniprot is None:
            result = Ligand.objects.filter(ids__index=str(id), ids__web_resource__slug=type, parent__isnull=False)
        else:
            result = Ligand.objects.filter(ids__index=str(id), ids__web_resource__slug=type, uniprot__contains=uniprot.upper(), parent__isnull=False)
    else:
        if uniprot is None:
            result = Ligand.objects.filter(ids__index=str(id), ids__web_resource__slug=type)
        else:
            result = Ligand.objects.filter(ids__index=str(id), ids__web_resource__slug=type, uniprot__contains=uniprot.upper())        

    if result.count() > 0:
        # For drugs we allow multiple entries because of stereochemistry if drug is racemic
        if result.count() > 1 and type not in ["drugbank", "drug_central", "pubchem"]:
            print("Multiple entries for the same ID - This should never happen - error", type, id)
        return result.first()
    else:
        return None

def create_ligand_from_id(name, type, id, lig_type):
    # create new ligand
    ligand = Ligand()
    ligand.name = name
    ligand.ambiguous_alias = False
    ligand.ligand_type = LigandType.objects.get_or_create(slug=slugify(lig_type), defaults={'name': lig_type})[0]

    # Obtain external data (if needed)
    try:

        # TODO - continue here and add peptide/protein support for web services

        if type == "sequence":
            ligand.sequence = sequence
        elif type == "uniprot":
            ligand.uniprot = id
        elif type == "smiles":
            ligand.smiles = id
        elif type == "pubchem":
            # check cache
            cache_dir = ['pubchem', 'cid', 'property']
            url = 'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/$index/property/IsomericSMILES,InChIKey/json'
            if ligand.name == "":
                url = 'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/$index/property/Title,IsomericSMILES,InChIKey/json'
            pubchem = fetch_from_web_api(url, id, cache_dir)

            if pubchem != False and pubchem['PropertyTable']['Properties'][0]:
                properties = pubchem['PropertyTable']['Properties'][0]
                if len(properties['IsomericSMILES'])>0:
                    ligand.smiles = properties['IsomericSMILES']
                if len(properties['InChIKey'])>0:
                    ligand.inchikey = properties['InChIKey']
                if ligand.name == "":
                    ligand.name = properties['Title']
        elif type == "gtoplig":
            # check cache
            cache_dir = ['guidetopharmacology', 'ligand_structure']
            url = 'http://www.guidetopharmacology.org/services/ligands/$index/structure'
            gtop = fetch_from_web_api(url, id, cache_dir)

            if gtop:
                if len(gtop["smiles"])>0:
                    ligand.smiles = gtop["smiles"]
                if len(gtop["inchiKey"])>0:
                    ligand.inchikey = gtop["inchiKey"]
                if len(gtop["oneLetterSeq"])>0 and len(gtop["oneLetterSeq"])<1000:
                    ligand.sequence = gtop["oneLetterSeq"]
                    url = 'https://www.guidetopharmacology.org/services/ligands/$index/databaseLinks?database=UniProtKB'
                    gtop_uniprot = fetch_from_web_api(url, id, cache_dir)
                    if gtop_uniprot and len(gtop["accession"])>0:
                        ligand.uniprot = gtop["accession"]
        elif type == "chembl_ligand":
            # check cache
            cache_dir = ['chembl', 'ligand_entry']
            url = 'https://www.ebi.ac.uk/chembl/api/data/molecule/$index/?format=json'
            chembl = fetch_from_web_api(url, id, cache_dir)

            # NOTE: canonical SMILES from ChEMBL are isomeric smiles
            if chembl and "molecule_structures" in chembl:
                if len(chembl["molecule_structures"]["canonical_smiles"]) > 0:
                    ligand.smiles = chembl["molecule_structures"]["canonical_smiles"]
                if len(chembl["molecule_structures"]["standard_inchi_key"]) > 0:
                    ligand.inchikey = chembl["molecule_structures"]["standard_inchi_key"]
            if ligand.name == "" and chembl and "pref_name" in chembl and chembl["pref_name"] is not None:
                ligand.name = chembl["pref_name"]
            elif ligand.name == "":
                ligand.name = id
    except:
        skip=True

    # perform RDkit calculations
    if lig_type == "small-molecule" and ligand.smiles is not None and ligand.smiles != "":
        input_mol = dm.to_mol(ligand.smiles, sanitize=True)
        if input_mol:
            # Check if InChIKey has been set
            if ligand.inchikey is None:
                ligand.inchikey = dm.to_inchikey(input_mol)

            # Check if cleaned InChIKey has been set
            # if ligand.clean_inchikey is None:
                # ligand.clean_inchikey = get_cleaned_inchikey(ligand.smiles)

            # Calculate RDkit properties
            ligand.mw = dm.descriptors.mw(input_mol)
            ligand.rotatable_bonds = dm.descriptors.n_rotatable_bonds(input_mol)
            ligand.hacc = dm.descriptors.n_hba(input_mol)
            ligand.hdon = dm.descriptors.n_hbd(input_mol)
            ligand.logp = dm.descriptors.clogp(input_mol)
        else:
            print("Issues with molecule", name)
            # TODO - try again if we have other IDs

        # Before storing - check one more time if we already have this ligand
        if ligand.inchikey is not None:
            checkligand = get_ligand_by_inchikey(ligand.inchikey)
            if checkligand is not None:
                return checkligand

        # if ligand.clean_inchikey is not None and ligand.clean_inchikey != ligand.inchikey:
        #     checkligand = get_ligand_by_inchikey(ligand.clean_inchikey)
        #     if checkligand is not None:
        #         return checkligand

        return ligand
    elif lig_type != "small-molecule" or type == "":
        if type == "smiles" and ligand.inchikey is None:
            input_mol = dm.to_mol(ligand.smiles, sanitize=True)
            if input_mol:
                ligand.inchikey = dm.to_inchikey(input_mol)
                if ligand.inchikey is not None:
                    checkligand = get_ligand_by_inchikey(ligand.inchikey)
                    if checkligand is not None:
                        return checkligand

        # Before storing - check one more time if we already have this ligand based on sequence
        # TODO implement this double check
        # https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/71728433/XML
        # USE LXML for parsing => https://stackoverflow.com/questions/21628290/parsing-xml-with-xpath-in-python-3


        # https://www.ebi.ac.uk/chembl/api/data/molecule/CHEMBL59?format=xml&_=1643906691331
        # https://www.ebi.ac.uk/chembl/api/data/molecule/CHEMBL266481?format=xml
        #=> PEPTIDE parse HELM notation => no uniprot

        return ligand
    else:
        # Ligand could not be created
        return None

def get_ligand_by_inchikey(inchikey):
    result = Ligand.objects.filter((Q(inchikey=inchikey) & Q(parent__isnull=False)))
    if result.count() > 0:
        if result.count() > 1:
            print("Multiple entries for the same InChIkey - This should never happen - error", inchikey)
        return result.first()
    else:
        return None

def get_cleaned_inchikey(smiles):
    inchikey = None
    try:
        input_mol = dm.to_mol(smiles, sanitize=True)
        if input_mol:
            # Sligthly odd set of steps to get optimal cleaned and dominant tautomer
            input_mol = dm.to_neutral(input_mol)
            input_mol = dm.fix_mol(input_mol)
            cleaned_smiles = dm.standardize_smiles(dm.to_smiles(input_mol), tautomer=True)
            cleaned_mol = dm.to_mol(cleaned_smiles, sanitize=False)
            inchikey = dm.to_inchikey(cleaned_mol)
    except:
        skip = True
    return inchikey

def resolve_pubchem_SID(sid):
    cache_dir = ['pubchem', 'ligand_sid']
    url = 'https://pubchem.ncbi.nlm.nih.gov/rest/pug/substance/sid/$index/cids/json'
    pubchem = fetch_from_web_api(url, sid, cache_dir)
    if pubchem and "InformationList" in pubchem and "Information" in pubchem["InformationList"]:
        for entry in pubchem["InformationList"]["Information"]:
            if "CID" in entry:
                return entry["CID"][0]
    return None

def is_float(element):
    try:
        float(element)
        return True
    except ValueError:
        return False

def standardize_smiles(smiles):
    """
    Converts a SMILES string to an RDKit molecule, standardizes it using
    the chembl_structure_pipeline, and returns the standardized molecule.
    """
    # Create an RDKit molecule from the SMILES:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        print(f"Invalid SMILES: {smiles}")
        return None

    # Standardize the molecule.
    # The function returns a tuple: (standardized_mol, standardization_status)
    std_mol = standardizer.standardize_mol(mol)

    # Optionally, you can remove stereochemistry (if that’s your goal):
    Chem.RemoveStereochemistry(std_mol)

    smiles = Chem.MolToSmiles(std_mol, isomericSmiles=False)

    return smiles

# Example usage:
# smiles_example = "CC(=O)OC1=CC=CC=C1C(=O)O"  # Aspirin (for example)
# std_mol = standardize_smiles(smiles_example)
# if status == 'OK':
#     print("Standardized SMILES:", Chem.MolToSmiles(std_mol))
# else:
#     print("Standardization status:", status)
#
# ### HOW TO USE IT
#
# # Two SMILES strings that depict the same molecule but with different stereochemistry:
# smiles1 = "CN1[C@H]2C[C@H](OC(=O)[C@H](CO)c3ccccc3)C[C@@H]1[C@@H]1O[C@H]12"
# smiles2 = "CN1C2CC(CC1C3C2O3)OC(=O)C(CO)C4=CC=CC=C4"
#
# # Standardize the molecules:
# std_mol1 = standardize_smiles(smiles1)
# std_mol2 = standardize_smiles(smiles2)
#
# # Convert standardized molecules to canonical SMILES:
# std_smiles1 = Chem.MolToSmiles(std_mol1, isomericSmiles=False)
# std_smiles2 = Chem.MolToSmiles(std_mol2, isomericSmiles=False)

def generate_parent(name, ids, lig_type):
    ligand = Ligand()
    ligand.name = name
    ligand.ambiguous_alias = False
    ligand.ligand_type = LigandType.objects.get_or_create(slug=slugify(lig_type), defaults={'name': lig_type})[0]

    if "sequence" in ids:
        ligand.sequence = ids["sequence"]
    if "uniprot" in ids:
        ligand.uniprot = ids["uniprot"]
    if "smiles" in ids:
        ligand.smiles = standardize_smiles(ids["smiles"])
    if "inchikey" in ids:
        head_inchi = ids["inchikey"].split('-')[0]
        ligand.clean_inchikey = head_inchi
        ligand.inchikey = ids["inchikey"]

    # perform RDkit calculations
    if lig_type == "small-molecule" and ligand.smiles is not None and ligand.smiles != "":
        input_mol = dm.to_mol(ligand.smiles, sanitize=True)
        if input_mol:
            # Check if InChIKey has been set
            if ligand.inchikey is None:
                inchi = dm.to_inchikey(input_mol)
                ligand.clean_inchikey = inchi.split('-')[0]
                ligand.inchikey = inchi

            # Calculate RDkit properties
            ligand.mw = dm.descriptors.mw(input_mol)
            ligand.rotatable_bonds = dm.descriptors.n_rotatable_bonds(input_mol)
            ligand.hacc = dm.descriptors.n_hba(input_mol)
            ligand.hdon = dm.descriptors.n_hbd(input_mol)
            ligand.logp = dm.descriptors.clogp(input_mol)

    ligand.parent = None
    ligand.save()
    return ligand

def try_get_parent(query_params):
    try:
        parent_obj = Ligand.objects.get(**query_params)
        return parent_obj
    except Ligand.MultipleObjectsReturned:
        if 'name__iexact' in query_params:
            query_params['name'] = query_params.pop('name__iexact')
            try:
                parent_obj = Ligand.objects.get(**query_params)
                return parent_obj
            except Ligand.DoesNotExist:
                return None
        else:
            return None
    except Ligand.DoesNotExist:
        return None


def check_name(smiles: str,
               inchi: str,
               name: str,
               retries: int = 5,
               backoff_factor: float = 1.0):
    """
    Look up the IUPAC name for `smiles` on PubChem if any of
    (smiles, inchi, mol_weight) differs from the stored parent.
    Retries on PUGREST.ServerBusy with exponential backoff.

    Returns the new name if found, otherwise the original `name`.
    """
    # 1) Fetch parent object or bail
    try:
        parent = Ligand.objects.get(name=name, parent__isnull=True)
    except Ligand.DoesNotExist:
        return name

    # 2) Compute RDKit molecular weight (or bail)
    try:
        mol = dm.to_mol(smiles, sanitize=True)
        if mol is None:
            return name
        mol_weight = dm.descriptors.mw(mol)
    except Exception:
        return name

    # 3) If nothing has changed, return early
    if (parent.smiles == smiles and
        parent.inchikey == inchi and
        abs(parent.mw - mol_weight) < 1e-6):
        return name

    # 4) Otherwise, fetch IUPAC name with retries
    for attempt in range(retries):
        try:
            compounds = pcp.get_compounds(smiles, namespace='smiles')
            if not compounds:
                return name
            new_name = compounds[0].iupac_name
            return new_name or name
        except PubChemHTTPError as e:
            if 'PUGREST.ServerBusy' in str(e):
                wait = backoff_factor * (2 ** attempt)
                time.sleep(wait)
                continue
            # any other HTTP error: give up
            return name
        except BadRequestError:
            return name

    # 5) All retries failed
    return name

def update_parent(parent, child):
    """
    1) If child.inchikey → clean collision, reassign to that existing parent.
    2) Update any missing fields (smiles, inchikey, clean_inchikey, etc.) on
       whichever parent record is now in play.
    3) Return the “true” parent record.
    """
    updated = False

    # ————————————————
    # 0) EARLY CLEAN‑KEY COLLISION / REASSIGN
    # ————————————————
    if child.inchikey and not parent.clean_inchikey:
        clean = child.inchikey.split('-', 1)[0]
        collision = (
            Ligand.objects
                 .filter(clean_inchikey=clean)
                 .exclude(pk=parent.pk)
                 .first()
        )
        if collision:
            print(f"clean_inchikey '{clean}' already on {collision.name!r}; "
                  f"switching to that record.")
            # rebind to the “correct” parent
            parent = collision
            # also update the FK on the child object
            child.parent = collision
            child.save(update_fields=['parent'])
            # now continue with filling-in on this new parent

    # ————————————————
    # 1) SMILES standardization
    # ————————————————
    if not parent.smiles and child.smiles:
        std = standardize_smiles(child.smiles)
        if std:
            parent.smiles = std
            updated = True
            print(f"→ {parent.name}: set smiles")

    # ————————————————
    # 2) inchikey
    # ————————————————
    if not parent.inchikey and child.inchikey:
        parent.inchikey = child.inchikey
        updated = True
        print(f"→ {parent.name}: set inchikey")

    # ————————————————
    # 3) clean_inchikey (now safe)
    # ————————————————
    if not parent.clean_inchikey and child.inchikey:
        clean = child.inchikey.split('-', 1)[0]
        parent.clean_inchikey = clean
        updated = True
        print(f"→ {parent.name}: set clean_inchikey '{clean}'")

    # ————————————————
    # 4) other standard fields
    # ————————————————
    for field in ['sequence', 'logp', 'mw', 'helm', 'uniprot', 'pdbe']:
        if not getattr(parent, field) and getattr(child, field):
            setattr(parent, field, getattr(child, field))
            updated = True
            print(f"→ {parent.name}: set {field}")

    # ————————————————
    # 5) save parent if needed
    # ————————————————
    if updated:
        try:
            parent.save()
        except IntegrityError as e:
            print(f"❗️ Unable to save {parent.name}: {e!r}")

    return parent


#### Block for fixing mismatched LigandType assignment in Ligand model

# map LigandType IDs:
SMALL_MOLECULE = LigandType.objects.get(slug='small-molecule')
PEPTIDE        = LigandType.objects.get(slug='peptide')
PROTEIN        = LigandType.objects.get(slug='protein')
UNKNOWN        = LigandType.objects.get(slug='na')

def predict_type(ligand):
    """
    Predict small-molecule vs peptide vs protein from
    the presence/length of sequence *or* the pattern of amide
    bonds in SMILES if sequence is missing.
    """
    seq = (ligand.sequence or '').strip()
    smiles = (ligand.smiles or '').strip()

    # 1) If we actually have a sequence, use length
    if seq:
        return PEPTIDE if len(seq) <= 15 else PROTEIN

    # 2) No sequence: look at SMILES
    if smiles:
        # count amide bonds (one per residue) in either orientation
        smiles_up = smiles.upper()
        count = (
            smiles_up.count('NC(=O)')
          + smiles_up.count('C(=O)N')
        )

        if count == 0:
            return SMALL_MOLECULE
        if count <= 15:
            return PEPTIDE
        return PROTEIN

    # 3) nothing to go on
    return UNKNOWN

def score(item):
    """
    Same as before: (ligand, predicted_type) → numeric score
    """
    lig, pred = item
    if pred in (PROTEIN, PEPTIDE):
        return len(lig.sequence or '')      # longer is better
    if pred == SMALL_MOLECULE:
        return -(len(lig.smiles or ''))     # shorter is better
    return float('-inf')

def pick_canonical_type(children):
    """
    Given a list of Ligand children, returns the string
    of the best ligand type (one of SMALL_MOLECULE, PEPTIDE, PROTEIN).
    """
    # 1) compute predictions
    pairs = []
    for lig in children:
        pred = predict_type(lig)
        pairs.append((lig, pred))

    # 2) split into “matched” vs “unmatched” against actual
    matched = []
    for lig, pred in pairs:
        actual = (lig.ligand_type.name.lower() if lig.ligand_type else UNKNOWN)
        if pred == actual:
            matched.append((lig, pred))

    if matched:
        candidates = matched
    else:
        # no actual matches → majority vote on predictions
        counts = Counter(pred for _, pred in pairs)
        most_common_pred, _ = counts.most_common(1)[0]
        candidates = [(lig, pred) for lig, pred in pairs if pred == most_common_pred]

    # 3) tie‐break by length heuristics
    best_lig, best_pred = max(candidates, key=score)
    return best_pred

def resolve_all_parents():
    """
    Find all parents with children of mixed types,
    and for each, choose the canonical child.
    Returns a dict: parent_id → (chosen_ligand, [all_children])
    """
    from django.db.models import Count

    # 1) find parent IDs with >1 distinct ligand_type among children
    mixed_parents = (
        Ligand.objects
              .filter(parent__isnull=False)
              .values('parent')
              .annotate(cnt=Count('ligand_type', distinct=True))
              .filter(cnt__gt=1)
              .values_list('parent', flat=True)
    )

    # 2) fetch all children for those parents
    qs = Ligand.objects.filter(parent_id__in=mixed_parents).select_related('ligand_type')

    # 3) group in Python
    by_parent = defaultdict(list)
    for child in qs:
        by_parent[child.parent_id].append(child)

    # 4) pick canonical for each
    result = {}
    for pid, kids in by_parent.items():
        result[pid] = (pick_canonical_type(kids), kids)

    return result

def apply_canonical_ligand_types():
    """
    For each parent with mixed‐type children,
    determines the canonical LigandType (via pick_canonical_child),
    then updates *all* those children—and the parent record itself—
    to use that LigandType.
    Returns the total number of rows updated.
    """
    mapping = resolve_all_parents()    # { parent_id: (best_type, [kids]) }
    total_updated = 0

    with transaction.atomic():
        for parent_id, (best_type, kids) in mapping.items():
            # collect children+p arent IDs
            ids = [c.pk for c in kids] + [parent_id]
            updated = Ligand.objects.filter(pk__in=ids).update(ligand_type=best_type)
            total_updated += updated

    return total_updated
