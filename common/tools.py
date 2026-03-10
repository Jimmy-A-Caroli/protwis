from django.conf import settings
from django.utils.text import slugify
from django.core.cache import cache

import os
import sys
import yaml
import time
import logging
import urllib
from urllib.parse import quote
from urllib.request import urlopen
from urllib.error import HTTPError
import hashlib
import json
import gzip
from io import BytesIO
from string import Template
from Bio import Entrez, Medline
import xml.etree.ElementTree as etree
from http.client import HTTPException


def test_model_updates(model, master_data, initialize=False, check=False, rerun=False):
    #check if the input is a single model or a list of models
    #and initialize the dictionary with the model name and length (set to 0)
    print(f'Initialize: {initialize}')
    if initialize:
        print('Initializing master database of built models')
        if len(model) == 1:
            if model[0] not in master_data.keys():
                master_data[model[0]] = model[0].objects.all().count()
        else:
            for table in model:
                if table not in master_data.keys():
                    master_data[table] = table.objects.all().count()
    if check:
        print(f'CHECKing... check = {check}')
        CHECK = True
        if len(model) == 1:
            OG = master_data[model[0]]
            NEW = model[0].objects.all().count()
            if NEW != OG:
                master_data[model[0]] = NEW
                print('Changes have been applied to the model: ' + str(model[0]))
                CHECK = True
                if NEW > OG:
                    diff = NEW - OG
                    print(str(diff) + ' records have been added')
                else:
                    diff = OG - NEW
                    print(str(diff) + ' records have been removed')
        else:
            for table in model:
                OG = master_data[table]
                NEW = table.objects.all().count()
                if NEW != OG:
                    master_data[table] = NEW
                    print('Changes have been applied to the model: ' + str(table))
                    CHECK = True
                    if NEW > OG:
                        diff = NEW - OG
                        print(str(diff) + ' records have been added')
                    else:
                        diff = OG - NEW
                        print(str(diff) + ' records have been removed')

        if not CHECK:
            print('EXITING: No module have been updated. Probably some error?')
            sys.exit()

    if rerun:
        print('Checking if changes have happened during a build rerun')
        if len(model) == 1:
            OG = master_data[model[0]]
            NEW = model[0].objects.all().count()
            if NEW != OG:
                print('Something had changed in the record of the model ' + str(model[0]))
                print('Previous number of records: ' +str(OG))
                print('New number of records: ' +str(NEW))
        else:
            for table in model:
                OG = master_data[table]
                NEW = table.objects.all().count()
                if NEW != OG:
                    print('Something had changed in the record of the model ' + str(table))
                    print('Previous number of records: ' +str(OG))
                    print('New number of records: ' +str(NEW))


def save_to_cache(path, file_id, data):
    create_cache_dirs(path)
    cache_dir_path = os.sep.join([settings.BUILD_CACHE_DIR] + path)
    cache_file_path = os.sep.join([cache_dir_path, file_id + '.yaml'])
    with open(cache_file_path, 'w') as cache_file:
        yaml.dump(data, cache_file, default_flow_style=False)

def fetch_from_cache(path, file_id):
    cache_dir_path = os.sep.join([settings.BUILD_CACHE_DIR] + path)
    cache_file_path = os.sep.join([cache_dir_path, file_id + '.yaml'])
    if os.path.isfile(cache_file_path):
        try:
            with open(cache_file_path) as cache_file:
                return yaml.load(cache_file, Loader=yaml.FullLoader)
        except TypeError as msg:
            print('WARNING: cannot properly open {} with TypeError: {}'.format(cache_file_path, msg))
            return None
    else:
        return None

def create_cache_dirs(path):
    cache_file_path = os.sep.join([settings.BUILD_CACHE_DIR] + path)
    os.makedirs(cache_file_path, exist_ok=True)
    intermediate_path = settings.BUILD_CACHE_DIR
    for directory in path:
        intermediate_path = os.sep.join([intermediate_path, directory])
        os.chmod(intermediate_path, 0o777)

def fetch_from_web_api(url, index, cache_dir=False, xml=False, raw=False):
    logger = logging.getLogger('build')

    # slugify the index for the cache filename (some indices have symbols not allowed in file names (e.g. /))
    index_slug= slugify(index)
    cache_file_path = '{}/{}'.format('/'.join(cache_dir), index_slug)

    # try fetching from cache
    if cache_dir:
        # d = cache.get(cache_file_path)
        d = fetch_from_cache(cache_dir, index_slug)
        if d:
            logger.info('Fetched {} from cache'.format(cache_file_path))
            return d

    # if nothing is found in the cache, use the web API
    full_url = Template(url).substitute(index=quote(str(index), safe=''))
    logger.info('Fetching {}'.format(full_url))
    tries = 0
    max_tries = 5
    while tries < max_tries:
        if tries > 0:
            logger.warning('Failed fetching {}, retrying'.format(full_url))

        try:
            req = urlopen(full_url)
            if full_url[-2:]=='gz' and xml:
                try:
                    buf = BytesIO( req.read())
                    f = gzip.GzipFile(fileobj=buf)
                    data = f.read()
                    d = etree.fromstring(data)
                except:
                    return False
            elif xml:
                try:
                    d = etree.fromstring(req.read().decode('UTF-8'))
                except:
                    return False
            elif raw:
                try:
                    d = req.read().decode('UTF-8')
                except:
                    return False
            else:
                d = json.loads(req.read().decode('UTF-8'))
        except HTTPError as e:
            tries += 1
            if e.code == 404:
                logger.warning('Failed fetching {}, 404 - does not exist'.format(full_url))
                tries = max_tries #skip more tries
                return False
            elif e.code == 400:
                logger.warning('Failed fetching {}, 400 - does not exist'.format(full_url))
                tries = max_tries #skip more tries
                return False
            else:
                time.sleep(2)
        except HTTPException as e:
            tries += 1
            time.sleep(2)
        except urllib.error.URLError as e:
            # Catches 101 network is unreachable -- I think it's auto limiting feature
            tries +=1
            time.sleep(2)
        else:
            # save to cache
            if cache_dir:
                save_to_cache(cache_dir, index_slug, d)
                # cache.set(cache_file_path, d, 60*60*24*7) #7 days
                logger.info('Saved entry for {} in cache'.format(cache_file_path))
            return d

    # give up if the lookup fails 5 times
    logger.error('Failed fetching {} {} times, giving up'.format(full_url, max_tries))
    return False

def get_or_create_url_cache(url, validity = -1):
    # Hash the url
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()

    # Check the cache if exists
    valid = True
    urlcache_dir = os.sep.join([settings.DATA_DIR, 'common_data','url_cache'])
    cache_file = os.sep.join([urlcache_dir, url_hash])
    if os.path.isfile(cache_file):
        # Check if the data is still valid if set
        if validity > 0:
            seconds = int(time.time()) - int(os.path.getctime(cache_file))
            valid = seconds < validity

        # return cached filepath when still valid
        if valid:
            return cache_file

    # Data not yet exists => collect data and store in cache
    response = urlopen_with_retry(url)
    if response:
        # Write new results to file cache
        with open(cache_file, 'wb') as f:
            f.write(response.read())
            f.close()
        return cache_file
    elif not valid:
        print("WARNING: file cache not valid anymore - but new version could not be downloaded")
        print("WARNING:", url)
        return cache_file

    # Data could not be obtained
    return False

def fetch_from_entrez(index, cache_dir=''):
    logger = logging.getLogger('build')

    # slugify the index for the cache filename (some indices have symbols not allowed in file names (e.g. /))
    index_slug= slugify(index)
    cache_file_path = '{}/{}'.format('/'.join(cache_dir), index_slug)

    # try fetching from cache
    if cache_dir:
        d = fetch_from_cache(cache_dir, index_slug)
        if d:
            logger.info('Fetched {} from cache'.format(cache_file_path))
            return d

    # if nothing is found in the cache, use the web API
    logger.info('Fetching {} from Entrez'.format(index))
    tries = 0
    max_tries = 2
    while tries < max_tries:
        if tries > 0:
            logger.warning('Failed fetching pubmed via Entrez {}, retrying'.format(str(index)))

        try:
            Entrez.email = 'info@gpcrdb.org'
            handle = Entrez.efetch(
                db="pubmed",
                id=str(index),
                rettype="medline",
                retmode="text"
            )
        except:
            tries += 1
            time.sleep(0.2)
        else:
            d = Medline.read(handle)

            # save to cache
            save_to_cache(cache_dir, index_slug, d)
            logger.info('Saved entry for {} in cache'.format(cache_file_path))
            return d

def urlopen_with_retry(url, data = None, retries = 5, sleeptime = 5):
    logger = logging.getLogger('build')

    # Try to request data from URL  for few seconds and retry X times
    for retry in range(retries):
        if retry > 0:
            time.sleep(sleeptime)

        response = None
        try:
            response = urlopen(url, data) #nosec
        except urllib.error.URLError as e:
            logger.warning(f'URLopen error (retry {retry} out of {retries}) {e}')

        if response != None and 200 <= response.code < 300:
            return response
        elif retry == retries:
            return False

def parse_uniprot_file(accession, path_to_file=False, logger=None, local_uniprot_dir=None, remote_uniprot_dir='http://www.uniprot.org/uniprot/', excel_sequences=None):
    filename = accession + '.txt'
    if not path_to_file:
        local_file_path = os.sep.join([local_uniprot_dir, filename])
    else:
        local_file_path = path_to_file
    remote_file_path = remote_uniprot_dir + filename

    up = {
        'genes': [],
        'names': [],            
        'accessions': [],
        'structures': [],
        'entrez_geneids': []
    }

    read_sequence = False
    remote = False

    # record whether organism has been read
    os_read = False

    # should local file be written?
    local_file = False

    try:
        if os.path.isfile(local_file_path):
            uf = open(local_file_path, 'r')
            if logger is not None: logger.info('Reading local file ' + local_file_path)
        else:
            uf = urlopen_with_retry(remote_file_path)
            if uf == False:
                if logger is not None: logger.warning(f'ERROR: UNIPROT file could not be obtained for {accession}')
                return False

            remote = True
            if logger is not None: logger.info('Reading remote file ' + remote_file_path)
            local_file = open(local_file_path, 'w')

        for raw_line in uf:
            # line format
            if remote:
                line = raw_line.decode('UTF-8')
            else:
                line = raw_line

            # write to local file if appropriate
            if local_file:
                local_file.write(line)

            # end of file
            if line.startswith('//'):
                break

            # entry name and review status
            if line.startswith('ID'):
                split_id_line = line.split()
                up['entry_name'] = split_id_line[1].lower()
                review_status = split_id_line[2].strip(';')
                if review_status == 'Unreviewed':
                    up['source'] = 'TREMBL'
                elif review_status == 'Reviewed':
                    up['source'] = 'SWISSPROT'

            # species
            elif line.startswith('OS') and not os_read:
                species_full = line[2:].strip().strip('.')
                species_split = species_full.split('(')
                up['species_latin_name'] = species_split[0].strip()
                if len(species_split) > 1:
                    up['species_common_name'] = species_split[1].strip().strip(')')
                else:
                    up['species_common_name'] = up['species_latin_name']
                os_read = True

            # accessions
            elif line.startswith('AC'):
                sline = line.split()
                for ac in sline:
                    up['accessions'].append(ac.strip(';'))

            # names
            elif line.startswith('DE'):
                split_de_line = line.split('=')
                if len(split_de_line) > 1:
                    split_segment = split_de_line[1].split('{')
                    up['names'].append(split_segment[0].strip().strip(';'))

            # genes
            elif line.startswith('GN'):
                split_gn_line = line.split(';')
                for segment in split_gn_line:
                    if '=' in segment:
                        split_segment = segment.split('=')
                        split_segment = split_segment[1].split(',')
                        for gene_name in split_segment:
                            split_gene_name = gene_name.split('{')
                            up['genes'].append(split_gene_name[0].strip())

            # # structures
            # elif line.startswith('DR') and 'PDB;' in line:
            #     split_gn_line = line.split(';')
            #     up['structures'].append([split_gn_line[1].lstrip(), split_gn_line[3].lstrip().split(" A")[0]])


            # NCBI IDs
            elif line.startswith('DR'):
                line_tagless = line[5:]                    
                split_dr_line = line_tagless.split(';')
                if split_dr_line[0].strip() == 'GeneID':
                    id = split_dr_line[1].strip()
                    if (id.isdecimal()):
                        up['entrez_geneids'].append(id)
                    else:
                        if logger is not None: logger.info('Encountered non-numeric entrez gene id :' + id + ' for protein ' + up['entry_name'] + ', skipping')

            # sequence
            elif line.startswith('SQ'):
                split_sq_line = line.split()
                seq_len = int(split_sq_line[2])
                read_sequence = True
                up['sequence'] = ''
            elif read_sequence == True:
                up['sequence'] += line.strip().replace(' ', '')

        # close the Uniprot file
        uf.close()
        try:
            up['sequence'] = excel_sequences[up['entry_name']]['Sequence']
        except:
            pass
    except:
        return False

    # close the local file if appropriate
    if local_file:
        local_file.close()

    return up