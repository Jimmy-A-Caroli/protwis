from django.core.management.base import BaseCommand, CommandError

from build.management.commands.build_human_residues import Command as BuildHumanResidues
from protein.models import Protein


class Command(BuildHumanResidues):
    help = 'Creates residue records for non-human receptors'

    pconfs = Protein.objects.exclude(species__id=1).prefetch_related(
        'protein__residue_numbering_scheme__parent')
