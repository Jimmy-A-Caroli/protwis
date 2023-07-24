# -*- coding: utf-8 -*-
"""
Created on 2020-11-13 10:16:25.482439

@author: Gaspar Pandy
"""
from build.management.commands.base_build import Command as BaseBuild
from django.conf import settings

# from common.alignment import Alignment
from protein.models import Protein, ProteinSegment
# from residue.models import Residue
from structure.models import Structure, StructureRMSD
from structure.sequence_parser import SequenceParser
from common.tools import test_model_updates
from datetime import datetime
import csv, os, pprint
import django.apps


starttime = datetime.now()

class Command(BaseBuild):

    #Setting the variables for the test tracking of the model upadates
    tracker = {}
    all_models = django.apps.apps.get_models()[6:]
    test_model_updates(all_models, tracker, initialize=True)
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser=parser)
        parser.add_argument('--verbose',
            action='store_true',
            default=False,
            help='Verbose')
        parser.add_argument('-u', '--purge',
            action='store_true',
            dest='purge',
            default=False,
            help='Purge existing records')

    def handle(self, *args, **options):
        bsmr = BuildStructureRMSD()
        if options['purge']:
            bsmr.purge()
            self.tracker = {}
            test_model_updates(self.all_models, self.tracker, initialize=True)
        bsmr.parse_data_file()
        bsmr.run_build()
        test_model_updates(self.all_models, self.tracker, check=True)


class BuildStructureRMSD():
    def __init__(self):
        self.data = []

    def purge(self):
        StructureRMSD.objects.all().delete()

    def parse_data_file(self):
        self.data_file = os.sep.join([settings.DATA_DIR, 'structure_data', 'model_rmsd.csv'])
        with open(self.data_file, newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            self.data = [i for i in reader]

    def run_build(self):
        for i in self.data[1:]:
            i = [None if j=='-' else float(j) if '.' in j and len(j)==3 else j for j in i]
            pdb, _, version, overall_all, overall_backbone, TM_all, TM_backbone, H8, ICL1, ECL1, ICL2, ECL2, ECL3, notes = i
            target_structure = Structure.objects.get(pdb_code__index=pdb.upper())
            main_template = None
            seq_id, seq_sim = None, None
            smr, created = StructureRMSD.objects.get_or_create(target_structure=target_structure,
                                                               main_template=main_template,
                                                               version='{}-{}-{}'.format(version[-4:], version[3:5], version[:2]),
                                                               seq_id=seq_id, seq_sim=seq_sim,
                                                               overall_all=overall_all, overall_backbone=overall_backbone, TM_all=TM_all,
                                                               TM_backbone=TM_backbone, H8=H8,
                                                               ICL1=ICL1, ECL1=ECL1, ICL2=ICL2, ECL2=ECL2, ECL3=ECL3,
                                                               notes=notes)
