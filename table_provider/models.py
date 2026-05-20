from django.db import models

class StructureModelStatisticsTable(models.Model):
    uniprot_entry_name = models.CharField(max_length=20, null=False)
    uniprot_accession = models.CharField(max_length=20, null=False)
    protein_name = models.CharField(max_length=100, null=False)
    receptor_family = models.CharField(max_length=100, null=True)
    receptor_class = models.CharField(max_length=100, null=True)
    gene_name = models.CharField(max_length=100, null=True)
    gene_entrez_id = models.CharField(max_length=100, null=True)
    species_common_name = models.CharField(max_length=100, null=True)

    # Structure counts by state
    st_inact_c = models.IntegerField(null=False)
    st_interm_c = models.IntegerField(null=False)
    st_act_c = models.IntegerField(null=False)

    # Best resolution by state
    best_res_inact = models.FloatField(null=True)
    best_res_interm = models.FloatField(null=True)
    best_res_act = models.FloatField(null=True)

    # Transducer / extra-protein counts
    transd_gio_c = models.IntegerField(null=False)
    transd_gq11_c = models.IntegerField(null=False)
    transd_g1213_c = models.IntegerField(null=False)
    transd_arrest_c = models.IntegerField(null=False)
    transd_grks_c = models.IntegerField(null=False)

    # Ligand type counts
    ligand_types_smmol_c = models.IntegerField(null=False)
    ligand_types_pep_c = models.IntegerField(null=False)

    # Modality group counts 
    limodgrp_stim_c = models.IntegerField(null=False)
    limodgrp_inhib_c = models.IntegerField(null=False)
    limodgrp_unk_c = models.IntegerField(null=False)

    # Individual modality counts
    limod_apo_c = models.IntegerField(null=False)
    limod_ag_c = models.IntegerField(null=False)
    limod_ag_partial_c = models.IntegerField(null=False)
    limod_allo_antag_c = models.IntegerField(null=False)
    limod_antag_c = models.IntegerField(null=False)
    limod_inv_ag_c = models.IntegerField(null=False)
    limod_nam_c = models.IntegerField(null=False)
    limod_pam_c = models.IntegerField(null=False)
    limod_unk_c = models.IntegerField(null=False)

    def __str__(self):
        str = f'''
            "uniprot_entry_name" : {self.uniprot_entry_name}, 
            "protein_name" : {self.protein_name},
            "receptor_family" : {self.receptor_family},
            "receptor_class" : {self.receptor_class},
            "gene_name" : {self.gene_name},
            "gene_entrez_id" : {self.gene_entrez_id},
            "species_common_name" : {self.species_common_name},
            "structure_inactive_c" : {self.st_inact_c },
            "structure_intermediate_c" : {self.st_interm_c },
            "structure_active_c" : {self.st_act_c },
            "best_resolution_inactive" : {self.best_res_inact },
            "best_resolution_intermediate" : {self.best_res_interm },
            "best_resolution_active" : {self.best_res_act },
            "transducer_gio_count" : {self.transd_gio_c },
            "transducer_gq11_count" : {self.transd_gq11_c },
            "transducer_g1213_count" : {self.transd_g1213_c },
            "transducer_arrest_count" : {self.transd_arrest_c },
            "transducer_grks_count" : {self.transd_grks_c },
            "ligand_types_smallmolecule_count" : {self.ligand_types_smmol_c },
            "ligand_types_peptide_count" : {self.ligand_types_pep_c },
            "limodgrp_stimulatory_count" : {self.limodgrp_stim_c },
            "limodgrp_inhibitory_count" : {self.limodgrp_inhib_c },
            "limodgrp_unknown_count" : {self.limodgrp_unk_c },
            "limod_apo_count" : {self.limod_apo_c },
            "limod_agonist_count" : {self.limod_ag_c },
            "limod_agonist_partial_count" : {self.limod_ag_partial_c },
            "limod_allosteric_antagonist_count" : {self.limod_allo_antag_c },
            "limod_antagonist_count" : {self.limod_antag_c },
            "limod_inverse_agonist_count" : {self.limod_inv_ag_c },
            "limod_negative_allosteric_modulators_count" : {self.limod_nam_c },
            "limod_positive_allosteric_modulators_count" : {self.limod_pam_c },
            "limod_unk_count" : {self.limod_unk_c },
            '''
        return "{" + str + "}"
            

    class Meta:
        db_table = "structure_model_statistics"
        indexes = [
                models.Index(fields=["uniprot_entry_name"], name="uniprot_entry_name_idx"),
                models.Index(fields=["protein_name"], name="protein_name_idx"),
                models.Index(fields=["receptor_family"], name="receptor_family_idx"),
                models.Index(fields=["receptor_class"], name="receptor_class_idx"),
                models.Index(fields=["gene_name"], name="gene_idx"),
                models.Index(fields=["species_common_name"], name="species_idx"),
                models.Index(fields=["st_inact_c"], name="st_inact_c_idx"),
                models.Index(fields=["st_interm_c"], name="st_interm_c_idx"),
                models.Index(fields=["st_act_c"], name="st_act_c_idx"),
                models.Index(fields=["best_res_inact"], name="best_res_inact_idx"),
                models.Index(fields=["best_res_interm"], name="best_res_interm_idx"),
                models.Index(fields=["best_res_act"], name="best_res_act_idx"),
                models.Index(fields=["transd_gio_c"], name="transd_gio_c_idx"),
                models.Index(fields=["transd_gq11_c"], name="transd_gq11_c_idx"),
                models.Index(fields=["transd_g1213_c"], name="transd_g1213_c_idx"),
                models.Index(fields=["transd_arrest_c"], name="transd_arrest_c_idx"),
                models.Index(fields=["transd_grks_c"], name="transd_grks_c_idx"),
                models.Index(fields=["ligand_types_smmol_c"], name="ligand_types_smmol_c_idx"),
                models.Index(fields=["ligand_types_pep_c"], name="ligand_types_pep_c_idx"),
                models.Index(fields=["limodgrp_stim_c"], name="limodgrp_stim_c_idx"),
                models.Index(fields=["limodgrp_inhib_c"], name="limodgrp_inhib_c_idx"),
                models.Index(fields=["limodgrp_unk_c"], name="limodgrp_unk_c_idx"),
                models.Index(fields=["limod_apo_c"], name="limod_apo_c_idx"),
                models.Index(fields=["limod_ag_c"], name="limod_ag_c_idx"),
                models.Index(fields=["limod_ag_partial_c"], name="limod_ag_partial_c_idx"),
                models.Index(fields=["limod_allo_antag_c"], name="limod_allo_antag_c_idx"),
                models.Index(fields=["limod_antag_c"], name="limod_antag_c_idx"),
                models.Index(fields=["limod_inv_ag_c"], name="limod_inv_ag_c_idx"),
                models.Index(fields=["limod_nam_c"], name="limod_nam_c_idx"),
                models.Index(fields=["limod_pam_c"], name="limod_pam_c_idx"),
                models.Index(fields=["limod_unk_c"], name="limod_unk_c_idx"),
        ]

