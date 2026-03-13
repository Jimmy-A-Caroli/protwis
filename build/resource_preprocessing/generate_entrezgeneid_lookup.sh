
#!/bin/bash
# This script downloads resources from NCBI and generates a lookup file mapping gene symbols and taxonomic IDs to Entrez Gene IDs and species names.

# Function to display usage
usage() {
    echo "Usage: $0 -u uniprot_dir -w working_dir -o outfile"
    echo "  -u uniprot_dir    Directory containing UniProt flat files"
    echo "  -w working_dir    Scratch directory for intermediates and output"
    echo "  -o outfile        Output file path"
    echo "  -t threads        Number of threads to use for parallel processing (default: 10)"
    echo "  -h                Display this help message"
    exit 1
}

threads=10

# Parse command line arguments
while getopts "u:w:o:t:h" opt; do
    case $opt in
        u) uniprot_dir="$OPTARG" ;;
        w) working_dir="$OPTARG" ;;
        o) outfile="$OPTARG" ;;
        t) threads="$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done

# Check if required arguments are provided
if [ -z "$uniprot_dir" ] || [ -z "$working_dir" ] || [ -z "$outfile" ]; then
    echo "Error: Missing required arguments."
    usage
fi

#download the gene2accession file from NCBI, which contains mappings between gene symbols and Entrez Gene IDs, as well as taxonomic information
if [ -e "${working_dir}/gene2accession.gz" ]
then
    echo "Found gene2accession.gz in working directory, skipping download. If you want to redownload, please remove the existing file and rerun the script."
else
    echo "Retrieving gene2accession.gz from NCBI FTP server..."
    curl ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/gene2accession.gz -o ${working_dir}/gene2accession.gz
fi

#download the taxonomy data dump files which various files with taxonomic information, including the mapping between taxonomic IDs and species names
if [ -e "${working_dir}/taxdump.tar.gz" ]
then
    echo "Found taxdump.tar.gz in working directory, skipping download. If you want to redownload, please remove the existing file and rerun the script."
else
    echo "Retrieving taxdump.tar.gz from NCBI FTP server..."
    curl ftp://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz -o ${working_dir}/taxdump.tar.gz
fi

#extract
echo "Extracting taxdump.tar.gz..."
cd ${working_dir} && tar -xf taxdump.tar.gz

mkdir -p ${working_dir}/batches
mkdir -p ${working_dir}/batches/processed

#Generate batches of 5000 files for parallel processing.
find ${uniprot_dir} -iname "*.txt" | sort | split -l 5000 - ${working_dir}/batches/uniprot_batch_ --additional-suffix=.txt 

#define function to extract taxonomic ID and gene symbol lines from uniprot files, and export it for use with parallel
extract_id_lines() {
        infile=$1
        outfile=$(dirname ${infile})/processed/$(basename ${infile} .txt)_idlines.txt
        cat ${infile}|
        while read -r f; 
        do 
            grep -E "^OX\s+NCBI_TaxID|^GN\s+Name" ${f}; 
        done > ${outfile}
}
export -f extract_id_lines

#Use parallel to process batches
parallel --jobs ${threads} extract_id_lines ::: ${working_dir}/batches/uniprot_batch_*.txt

#Merge batch outputs
cat ${working_dir}/batches/processed/*_idlines.txt > ${working_dir}/uniprot_taxid_genesymbol_intermediate.txt

#cleanup batch files
rm -fr ${working_dir}/batches

#Use awk to create two intermediate files: one with unique taxonomic IDs and another with unique gene symbols (including synonyms) from the uniprot files.  
awk \
    -v FILEa=${working_dir}/unique_taxid_list.txt \
    -v FILEb=${working_dir}/unique_genesymbol_list.txt \
    'BEGIN{
        FS="\t"; OFS="\t"
    } 
  
    /^OX/{
        match($0, "^OX[[:space:]]+NCBI_TaxID=([0-9]+) ?[{;].*$", match_array); 
        entrez_taxid = match_array[1];
        if (entrez_taxid != "") { print entrez_taxid >> FILEa } 
        if (entrez_taxid == "") { print ($0, "- taxid - empty") } 
    }

  /^GN.+Synonyms=/{
        match($0, "^GN[[:space:]]+Name=([^{;]+)[[:space:]]?[^;]*;[[:space:]]Synonyms=([^{;]+)[^;]*[[:space:]]?;.*", match_array)
        gene_symbol = match_array[1];
        synonyms = match_array[2];
        split(synonyms, syn_array, ", ");
        if (gene_symbol != "") { print gene_symbol >> FILEb } 
        if (gene_symbol == "") { print ($0, "- gene_symbol - empty")} 
        for (i in syn_array) {
                if (syn_array[i] != "") { print syn_array[i] >> FILEb } 
                if (syn_array[i] == "") { print ($0, "- gene_symbol_synonym - empty") } 
            }
    }
    
    /^GN/{
        match($0, "^GN[[:space:]]+Name=([^{;]+)[[:space:]]?[{;].*$", match_array)
        gene_symbol = match_array[1];
          if (gene_symbol != "") { print gene_symbol >> FILEb } 
        if (gene_symbol == "") { print ($0, "- gene_symbol - empty") } 
        }' ${working_dir}/uniprot_taxid_genesymbol_intermediate.txt


sort -n ${working_dir}/unique_taxid_list.txt | uniq > temp.txt && mv temp.txt ${working_dir}/unique_taxid_list.txt
sort -n ${working_dir}/unique_genesymbol_list.txt | uniq > temp.txt && mv temp.txt ${working_dir}/unique_genesymbol_list.txt

#Account for incorrect human gene name in uniprot file.
echo "NPY6RP" >> ${working_dir}/unique_genesymbol_list.txt #Uniprot file for Q99463 currently uses outdated NPY6R gene symbol instead of corrrect NPY6RP  

#Add end anchor to each gene symbol so it only matches the last column containing the gene symbol
sed -i "s/[[:space:]]*$/$/" ${working_dir}/unique_genesymbol_list.txt

#Extract lines from gene2accession file that contain gene symbols that appear in our uniprot files
echo "Preliminary filtering of gene2accession file for gene symbols of interest..."
zgrep -f ${working_dir}/unique_genesymbol_list.txt ${working_dir}/gene2accession.gz > ${working_dir}/entrez_of_interest_intermediate.txt

#Extract the mapping between taxonomic IDs and species names from the taxonomy dump file
echo "Extracting scientific names from taxonomy dump..."
grep scientific names.dmp | 
	sed "s/\t//g" | 
	cut -f1,2 -d'|' | 
	tr "|" "\t" > ${working_dir}/taxid_speciesname_mapping.txt

#Embedded python script to combine the data and produce a final mapping between gene symbols, taxonomic IDs, Entrez Gene IDs, and species names for the genes of interest
python3 <<-EOF
with open("${working_dir}/unique_taxid_list.txt") as tax_fh:
    tax_ids = [line.strip() for line in tax_fh]

with open("${working_dir}/unique_genesymbol_list.txt") as symbol_fh:
    gene_symbols = [line.strip().strip('$') for line in symbol_fh]

tax_id_dict = dict()
with open("${working_dir}/taxid_speciesname_mapping.txt") as tax_name_fh:
    for line in tax_name_fh:
        tax_id, species_name = line.strip().split('\t')
        tax_id_dict[tax_id] = species_name

outfile_fh = open("${working_dir}/entrez_of_interest_clean.txt", "w")
outfile_fh.write('gene_symbol\ttaxon_id\tentrez_gene_id\tspecies_name\n')	

print('Final filtering and output ...')
with open("${working_dir}/entrez_of_interest_intermediate.txt") as entrez_fh:
    line_counter = 0
    for line in entrez_fh:
        line_counter += 1
        try:
            line_split = line.strip().split('\t')
            tax_id = line_split[0]
            gene_id = line_split[1]
            symbol = line_split[15]
            species = tax_id_dict[tax_id]
            if symbol in gene_symbols and tax_id in tax_ids:
                outfile_fh.write(f'{symbol}\t{tax_id}\t{gene_id}\t{species}\n')
        except:
            print("Caught malformed line on line number:" + str(line_counter) + ".  Possible grep artifact. Skipping line.")
EOF

#remove duplicates to create final list
(head -n 1 ${working_dir}/entrez_of_interest_clean.txt && tail -n +2 ${working_dir}/entrez_of_interest_clean.txt | sort | uniq) > ${outfile}

#Account for incorrect human gene name in uniprot file.
echo "NPY6R#9606#4888#Homo sapiens" | tr '#' '\t' >> ${outfile} #Uniprot file for Q99463 currently uses outdated NPY6R gene symbol instead of corrrect NPY6RP  

cleanup
echo "Cleaning up ..."
if [ -e "${working_dir}/entrez_id_lookup.txt" ]
then
    rm ${working_dir}/*.dmp \
    ${working_dir}/*.prt \
    ${working_dir}/entrez_of_interest_clean.txt \
    ${working_dir}/readme.txt \
    ${working_dir}/entrez_of_interest_intermediate.txt \
    ${working_dir}/taxid_speciesname_mapping.txt \
    ${working_dir}/unique_genesymbol_list.txt \
    ${working_dir}/unique_taxid_list.txt \
    ${working_dir}/uniprot_taxid_genesymbol_intermediate.txt
fi