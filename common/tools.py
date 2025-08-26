from django.conf import settings
from django.utils.text import slugify
from django.core.cache import cache
from django.apps import apps
from difflib import get_close_matches
from common import definitions
from io import BytesIO
from string import Template
from Bio import Entrez, Medline
from http.client import HTTPException
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen
from urllib.error import HTTPError
from typing import List, Tuple, Optional, Dict
import re
import os
import sys
import yaml
import time
import logging
import urllib
import hashlib
import json
import gzip
import csv
import datetime as dt
import math
import xml.etree.ElementTree as etree

def dump_checker(model_label, record_count=None):
    """
    One-shot helper:
      1) Finds the latest dump in `dump_path` for `model_label`.
      2) Compares latest dump's data-row count vs `record_count`.
         - If `record_count` is None, it will query the DB count.
      3) If grown, writes a new CSV: {app_model}_{YYYY_MM_DD}.csv (overwrites same-day).
    Returns:
      {
        'latest_dump': <str|None>,
        'latest_count': <int>,
        'written': <bool>,
        'new_dump': <str|None>
      }
    """
    # ---- config & naming ----
    dump_path = os.sep.join([settings.DATA_DIR, 'model_snapshots'])
    safe = model_label.replace('.', '_').lower()

    # ---- find latest dump ----
    latest_path, latest_date, latest_n = None, None, -1
    if os.path.isdir(dump_path):
        for fname in os.listdir(dump_path):
            if not (fname.startswith(safe + "_") and fname.endswith(".csv")):
                continue
            m = re.match(r'^' + re.escape(safe) + r'_(\d{4})[-_](\d{2})[-_](\d{2})(?:__(\d+))?\.csv$', fname)
            if not m:
                continue
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                dte = dt.date(y, mo, d)
            except ValueError:
                continue
            n = int(m.group(4)) if m.group(4) else 0
            if (latest_date is None) or (dte > latest_date) or (dte == latest_date and n > latest_n):
                latest_date, latest_n = dte, n
                latest_path = os.path.join(dump_path, fname)

    # ---- count rows in latest dump (data lines only) ----
    latest_count = 0
    if latest_path and os.path.isfile(latest_path):
        with open(latest_path, "r", encoding="utf-8", newline="") as fh:
            line_no = -1
            for line_no, _ in enumerate(fh, 0):
                pass
            latest_count = max(line_no, 0)  # minus header -> we started at 0, so header is line 0

    # ---- get current count if not provided ----
    if record_count is None:
        app_label, model_name = model_label.split(".", 1)
        Model = apps.get_model(app_label, model_name)
        record_count = Model._default_manager.count()

    # ---- if not grown, stop ----
    if record_count <= latest_count:
        print('Found an existing dump, loading it in the output of the function')
        return {
            "latest_dump": latest_path,
            "latest_count": latest_count,
            "written": False,
            "new_dump": None,
        }

    # ---- write fresh dump (overwrite same-day) ----
    os.makedirs(dump_path, exist_ok=True)
    today = dt.date.today().strftime("%Y_%m_%d")
    out_path = os.path.join(dump_path, f"{safe}_{today}.csv")

    app_label, model_name = model_label.split(".", 1)
    Model = apps.get_model(app_label, model_name)
    fields = list(Model._meta.concrete_fields)
    columns = [getattr(f, "attname", f.name) for f in fields]
    pk = Model._meta.pk.attname
    qs = Model._default_manager.all().order_by(pk).values_list(*columns)

    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(columns)
        for row in qs.iterator():
            out_row = []
            for v in row:
                if v is None:
                    out_row.append("")
                elif isinstance(v, (dt.date, dt.datetime, dt.time)):
                    out_row.append(v.isoformat())
                else:
                    out_row.append(str(v))
            w.writerow(out_row)

    print('Dump has been successfully updated!')
    return {
        "latest_dump": latest_path,
        "latest_count": latest_count,
        "written": True,
        "new_dump": out_path,
    }

def test_model_updates(model, master_data, initialize=False, check=False, rerun=False, rebuild=False):
    #check if the input is a single model or a list of models
    #and initialize the dictionary with the model name and length (set to 0)
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
        CHECK = False
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
            if rebuild:
                print('No module have been updated. Previous rebuild covered whole data')
            else:
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
                return yaml.load(cache_file, Loader=yaml.Loader)
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

def find_role(role_str, fuzzy_cutoff=0.75):
    from ligand.models import LigandRole
    role_dict = definitions.ROLE_DICTIONARY
    # Pre‐compile your regex patterns once
    _role_patterns = []
    for role_type, subs in role_dict.items():
        for sub_key, synonyms in subs.items():
            escaped = [re.escape(s) for s in synonyms if s]
            if not escaped:
                continue
            _role_patterns.append((
                re.compile(r'\b(?:' + '|'.join(escaped) + r')\b', re.IGNORECASE),
                sub_key
            ))

    # Flatten all canonical sub_keys for fuzzy matching
    _all_sub_keys = [
        sub_key
        for subs in role_dict.values()
        for sub_key in subs.keys()
    ]
    # 1) Regex‐based exact/insensitive match
    for pattern, sub_key in _role_patterns:
        if pattern.search(role_str):
            return LigandRole.objects.filter(name=sub_key)

    # 2) Fuzzy‐string fallback
    candidates = get_close_matches(role_str, _all_sub_keys, n=1, cutoff=fuzzy_cutoff)
    if candidates:
        return LigandRole.objects.filter(name=candidates[0])

    # 3) Default to “Unknown”
    #    Assumes you’ve already bulk‐created a LigandRole with name='Unknown'
    return LigandRole.objects.filter(name='Unknown')

# -------------------
# Normalization maps
# -------------------
N_TERM_MAP = {
    "deamination": "Deamination",
    "deamidation": "Deamidation",
    "acetylation": "Acetyl",
    "ac (acetylation)": "Acetyl",
    "acyl": "Acyl",
    "butanoyl": "Butanoyl",
    "hexanoic acid": "HexanoicAcid",
    "nh2": "Amine",
    "n-term mod": "NtermMod",
}

C_TERM_MAP = {
    "nh2": "Amide",
    "nh2 (amidation)": "Amide",
    "nh2(amidation)": "Amide",
    "nh2-amidation": "Amide",
    "oh": "Hydroxyl",
    "-oh": "Hydroxyl",
    "oh-hydroxylation": "Hydroxyl",
}

# -------------------
# Patterns & helpers
# -------------------
DEAMINO_PREFIX_RE = re.compile(r"^\s*\(?\s*1?-?\s*deamino\)?-?\s*", re.IGNORECASE)
CYCLIC_FLAG_LEADING_RE = re.compile(r"^\s*c\[[^\]]+\]\s*", re.IGNORECASE)

LINKER_TOKEN_RE = re.compile(
    r"^(?:PEGO|PEDG\d+|PEG|AF\d{2,3}|Cy5|Cy7|125IY|99mTc|111In|DOTA)$",
    re.IGNORECASE,
)

def _norm(s: Optional[str]) -> Optional[str]:
    return s.lower().replace("\n", "").strip() if isinstance(s, str) else None

def parse_cycl_pos(s: Optional[str]) -> List[Tuple[int, int]]:
    if s is None:
        return []
    s = str(s).strip()
    if not s:
        return []
    out = []
    for part in re.split(r"[;,/]\s*", s):
        m = re.match(r"^\s*(\d+)\s*[-+]\s*(\d+)\s*$", part)
        if m:
            out.append((int(m.group(1)), int(m.group(2))))
    return out

def preclean_and_extract_terminals(seq: str):
    """
    - remove a *leading* 'c[...]' macro flag (we rely on explicit cyclizations)
    - extract inline N-term (Ac-, Acetyl-, (deamino)-) and C-term (-NH2, -OH)
    - very mild brace/paren fixes; no destructive global replacements
    """
    notes: Dict[str, bool] = {}
    s = (seq or "").strip()
    if not s or s.lower() == "nan":
        return "", None, None, notes

    # Drop a *leading* c[...] macro marker if present
    s2 = CYCLIC_FLAG_LEADING_RE.sub("", s)
    if s2 != s:
        notes["drop_leading_c_macro"] = True
        s = s2

    # Extract N-term inline
    n_term_from_seq = None
    if s.startswith("Ac-") or s.startswith("Acetyl-"):
        n_term_from_seq = "Acetylation"
        s = s.split("-", 1)[1]
        notes["n_from_seq"] = True
    else:
        s3 = DEAMINO_PREFIX_RE.sub("", s)
        if s3 != s:
            n_term_from_seq = "Deamination"
            s = s3
            notes["n_from_seq"] = True

    # Extract C-term inline
    c_term_from_seq = None
    if s.endswith("-NH2"):
        c_term_from_seq = "NH2 (Amidation)"
        s = s[:-4]
        notes["c_from_seq"] = True
    elif s.endswith("-OH"):
        c_term_from_seq = "OH"
        s = s[:-3]
        notes["c_from_seq"] = True

    # Trim whitespace artifacts
    s = re.sub(r"\s+", "", s)

    # Normalize 'c[' macros occurring mid-sequence into '[' (so we can expand them)
    # (We only remove the 'c' if it's exactly 'c[' not part of a name.)
    s = re.sub(r"c\[", "[", s)

    return s, n_term_from_seq, c_term_from_seq, notes

# ---- balanced scanning helpers ----
def _find_matching(s: str, start: int, open_ch="(", close_ch=")")->int:
    """Return index of matching close for s[start]==open_ch, or -1 if unbalanced."""
    assert s[start] == open_ch
    depth = 0
    for i in range(start, len(s)):
        if s[i] == open_ch:
            depth += 1
        elif s[i] == close_ch:
            depth -= 1
            if depth == 0:
                return i
    return -1

def expand_repeats_nested(s: str) -> str:
    """
    Expand '(... )n' even with nested parens in the unit.
    Also expand '[((...))n]' -> '((...))' repeated n times (brackets removed).
    Does not strip other parentheses.
    """
    # First handle bracketed repeat wrappers like [(unit)7]
    i = 0
    out = []
    while i < len(s):
        if s[i] == "[" and i+1 < len(s) and s[i+1] == "(":
            j = _find_matching(s, i+1, "(", ")")
            if j != -1:
                # read number before the closing bracket
                k = j + 1
                m = re.match(r"(\d+)\]", s[k:k+10])  # short lookahead window
                if m:
                    n = int(m.group(1))
                    unit = s[i+1:j+1]  # includes surrounding parentheses
                    out.append(unit * n)
                    i = k + len(m.group(0))  # past 'n]'
                    continue
        out.append(s[i])
        i += 1
    s = "".join(out)

    # Then handle plain (unit)n
    i = 0
    res = []
    while i < len(s):
        if s[i] == "(":
            j = _find_matching(s, i, "(", ")")
            if j != -1:
                # digits immediately after ')'
                m = re.match(r"(\d+)", s[j+1:j+6])
                if m:
                    n = int(m.group(1))
                    unit = s[i:j+1]  # keep the parentheses in the unit
                    res.append(unit * n)
                    i = j + 1 + len(m.group(1))
                    continue
        res.append(s[i])
        i += 1
    return "".join(res)

def split_by_mid_linkers(seq: str):
    """
    Split into alternating peptide parts and mid-linker CHEMs.
    We look for parentheses '(TOKEN)' that match LINKER_TOKEN_RE.
    Returns (peptide_parts, linkers)
    """
    peptide_parts: List[str] = []
    linkers: List[str] = []
    pos = 0
    for m in re.finditer(r"\(([^)]+)\)", seq):
        token = m.group(1)
        if LINKER_TOKEN_RE.match(token):
            chunk = seq[pos:m.start()]
            if chunk:
                peptide_parts.append(chunk)
            linkers.append(token)
            pos = m.end()
    tail = seq[pos:]
    if tail:
        peptide_parts.append(tail)
    if not linkers:
        return [seq], []
    return peptide_parts, linkers

def _tokenize_peptide_part(sequence: str):
    """
    For a peptide-only chunk (no mid-linkers left):
      - collect leading '(...)' caps → CHEMcap chain
      - residues are: single A–Z letters, 'dX' D-amino acids, or bracketed monomers '[..]'
      - bracket *sequence* like '[CRDFF...]' is expanded to letters; monomers like '[Nle]' kept as one
    """
    s = sequence.strip()

    leading_caps: List[str] = []
    # Pull off leading '(...)' blocks (caps) only at the N-terminus of this chunk
    while s.startswith("("):
        j = _find_matching(s, 0, "(", ")")
        if j == -1:
            break
        leading_caps.append(s[1:j])  # content only
        s = s[j+1:]

    residues: List[str] = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "[":
            j = s.find("]", i+1)
            if j == -1:
                raise ValueError("Unmatched '[' in sequence part: " + sequence)
            inner = s[i+1:j]
            # If inner is a pure peptide fragment (A–Z or X only), expand into letters
            if re.fullmatch(r"[A-ZX]+", inner):
                residues.extend(list(inner))
            else:
                residues.append("[" + inner + "]")
            i = j + 1
            continue
        if ch == "(":
            # mid annotations: skip over the balanced block
            j = _find_matching(s, i, "(", ")")
            i = (j + 1) if j != -1 else (i + 1)
            continue
        if ch == "d" and i+1 < n and s[i+1].isalpha() and s[i+1].isupper():
            residues.append(s[i:i+2])  # e.g., 'dC'
            i += 2
            continue
        if ch.isalpha() and ch.isupper():
            residues.append(ch)
        i += 1
    return leading_caps, residues

def _attach_caps_and_terms(poly_name, residues, leading_caps, n_term, c_term,
                           polymers, chems, conns, name_counters):
    """
    Build polymer for one peptide chunk and attach caps + (first/last) terminals.
    """
    polymers.append(f"{poly_name}{{{'.'.join(residues)}}}")

    # N-anchor for this peptide chunk
    anchor_poly = poly_name
    anchor_site = "1:R1"

    # Caps (N-end of THIS chunk)
    for idx, cap in enumerate(leading_caps, start=1):
        cap_name = f"CHEMcap_{poly_name}_{idx}"
        chems.append((cap_name, cap))
        conns.append(f"{anchor_poly},{cap_name},{anchor_site}-1:R2")
        anchor_poly, anchor_site = cap_name, "1:R1"

    # N-term mod (only for first chunk)
    nm = _norm(n_term)
    if nm:
        nmon = N_TERM_MAP.get(nm, (n_term or "").strip())
        name_counters["CHEMN"] += 1
        chemn = f"CHEMN_{name_counters['CHEMN']}"
        chems.append((chemn, nmon))
        conns.append(f"{anchor_poly},{chemn},{anchor_site}-1:R1")

    # C-term mod (only for last chunk)
    cm = _norm(c_term)
    if cm:
        cmon = C_TERM_MAP.get(cm, (c_term or "").strip())
        name_counters["CHEMC"] += 1
        chemc = f"CHEMC_{name_counters['CHEMC']}"
        chems.append((chemc, cmon))
        conns.append(f"{poly_name},{chemc},{len(residues)}:R2-1:R2")

    return poly_name, len(residues)

def _auto_shift_if_parent_numbering(i, j, total, max_shift=5):
    """
    If either i or j exceeds total but looks like a uniform shift from a parent sequence,
    try shifting both by the same amount (1..max_shift). Return (i2,j2) or None.
    """
    overshoot = max(i, j) - total
    if overshoot < 1 or overshoot > max_shift:
        return None
    i2, j2 = i - overshoot, j - overshoot
    if 1 <= i2 <= total and 1 <= j2 <= total:
        return (i2, j2)
    return None

def generate_helm_universal(
    sequence: str,
    n_term: Optional[str] = None,
    c_term: Optional[str] = None,
    cyclizations: Optional[List[Tuple[int, int]]] = None,
    cyclization_type: Optional[str] = None,   # still modeled R3–R3
    polymer_prefix: str = "PEPTIDE",
    auto_shift_indices: bool = True,
) -> Optional[str]:
    """
    Generalized HELM generator:
      - pre-cleans sequence; extracts inline terminals
      - expands nested repeats
      - splits mid-linkers (PEGO/PEDGxx/PEG/AFxx/Cy5/Cy7/125IY/99mTc/111In/DOTA) as CHEM bridges
      - flattens c[PEPTIDE] blocks into residues when bracket content is plain letters
      - builds global residue map so cyclizations can span blocks
      - ensures unique CHEM polymer names
      - returns None (and prints a precise message) when cyclization indices cannot be reconciled
    """
    if not isinstance(sequence, str) or not sequence.strip():
        raise ValueError("Empty sequence")

    # Pre-clean & inline terminals
    s, n_from_seq, c_from_seq, _notes = preclean_and_extract_terminals(sequence)
    n_term = n_term or n_from_seq
    c_term = c_term or c_from_seq

    # Expand repeats (nested safe)
    s = expand_repeats_nested(s)

    # Split by linkers
    peptide_chunks, linkers = split_by_mid_linkers(s)

    # Build sections
    polymers: List[str] = []
    chems: List[Tuple[str, str]] = []
    conns: List[str] = []
    poly_names: List[str] = []
    lengths: List[int] = []
    global_map: List[Tuple[str, int]] = []
    name_counters = {"CHEMN": 0, "CHEMC": 0}

    # Tokenize & assemble each peptide chunk
    real_chunk_idx = 0
    for idx, chunk in enumerate(peptide_chunks, start=1):
        leading_caps, residues = _tokenize_peptide_part(chunk)
        if not residues:
            # Skip empty chunks (e.g., linker at start)
            continue
        real_chunk_idx += 1
        poly_name = f"{polymer_prefix}{real_chunk_idx}"
        poly_names.append(poly_name)

        # Apply N-term only to first *real* peptide, C-term to last
        apply_n = n_term if real_chunk_idx == 1 else None
        apply_c = c_term if real_chunk_idx == sum(1 for ch in peptide_chunks if _tokenize_peptide_part(ch)[1]) else None

        used_poly, L = _attach_caps_and_terms(
            poly_name=poly_name,
            residues=residues,
            leading_caps=leading_caps,
            n_term=apply_n,
            c_term=apply_c,
            polymers=polymers,
            chems=chems,
            conns=conns,
            name_counters=name_counters,
        )
        lengths.append(L)
        for j in range(1, L + 1):
            global_map.append((used_poly, j))

    # Bridge with linkers in order between *real* peptide blocks
    # We connect PEPTIDEk -- CHEMlink_k -- PEPTIDE(k+1)
    real_count = len(poly_names)
    real_idx = 0
    linker_idx = 0
    for token in linkers:
        # Only bridge when we have a next real peptide
        if real_idx + 1 >= real_count:
            break
        linker_idx += 1
        chem_name = f"CHEMlink_{linker_idx}"
        chems.append((chem_name, token))
        left_poly = poly_names[real_idx]
        left_len = lengths[real_idx]
        right_poly = poly_names[real_idx + 1]
        # connect C(left) -> linker -> N(right)
        conns.append(f"{left_poly},{chem_name},{left_len}:R2-1:R1")
        conns.append(f"{chem_name},{right_poly},1:R2-1:R1")
        real_idx += 1

    # Cyclizations (global indices)
    if cyclizations:
        total_res = sum(lengths)
        for (i_pos, j_pos) in cyclizations:
            if not (1 <= i_pos <= total_res and 1 <= j_pos <= total_res):
                # try auto-shift when it looks like parent numbering
                shifted = _auto_shift_if_parent_numbering(i_pos, j_pos, total_res) if auto_shift_indices else None
                if shifted is None:
                    print(f"Cyclization index out of bounds (global): ({i_pos}, {j_pos}) / total {total_res} for sequence {sequence}. Data provided {c_term}, {n_term}, {cyclizations}, {cyclization_type}")
                    return None
                i_pos, j_pos = shifted
            (pi, li) = global_map[i_pos - 1]
            (pj, lj) = global_map[j_pos - 1]
            conns.append(f"{pi},{pj},{li}:R3-{lj}:R3")

    # Assemble HELM
    polymers_section = "|".join(polymers + [f"{nm}{{{lbl}}}" for (nm, lbl) in chems])
    helm = f"{polymers_section}${'|'.join(conns)}$$" if conns else f"{polymers_section}$$$$"
    return helm
