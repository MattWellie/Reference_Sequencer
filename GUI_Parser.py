#Complete overhaul of original version
import sys
from Bio import SeqIO
import xml.etree.ElementTree as etree
import os

class Parser:

    '''
    Class version: 0.2
    Modified Date: 10/01/2015
    Author : Matt Welland
    
    Notes:
        Majority of variable storage change to dictionary entries
        -   This replaces the list storage of initial draft
        Final working version for LRG files, pending check with users
        Checked with clinical scientists, .gbk variant required
    '''

    def __init__(self, file_name, padding, existingfiles, file_type):#, root, option):
        self.fileName = file_name
        #Read in the specified input file into a variable
        try:
            self.file_type = file_type
            self.transcriptdict = {}
            self.transcriptdict['transcripts'] = {}
            if self.file_type == 'lrg':
                self.tree = etree.parse(self.fileName)
                self.transcriptdict['root'] = self.tree.getroot()
                self.transcriptdict['fixannot'] = self.transcriptdict['root'].find('fixed_annotation') #ensures only exons from the fixed annotation will be taken
                self.transcriptdict['genename'] = self.transcriptdict['root'].find('updatable_annotation/annotation_set/lrg_locus').text    
                self.transcriptdict['refseqname'] = self.transcriptdict['root'].find('fixed_annotation/sequence_source').text
                if self.transcriptdict['root'].attrib['schema_version'] <> '1.9':
                    print 'This LRG file is not the correct version for this script'
                    print 'This is designed for v.1.8'
                    print 'This file is v.' + self.root.attrib['schema_version']
            elif self.file_type == 'gbk':
                #Do this instead
                print 'GBK'
                self.transcriptdict['input'] = SeqIO.to_dict(SeqIO.parse(file_name,'genbank'))
                self.transcriptdict['refseqname'] = self.transcriptdict['input'].keys()[0]
                self.transcriptdict['transcripts'][1] = {}
                self.transcriptdict['transcripts'][1]['exons'] = {}
                               
            self.existingFiles = existingfiles
            self.transcriptdict['pad'] = int(padding)
            self.transcriptdict['pad_offset'] = int(padding) % 5
            self.amino_printing = False
            self.amino_spacing = False
            self.exon_spacing = False
            self.exon_printed = False
            self.dont_print = False
            self.is_matt_awesome = True
        except IOError as fileNotPresent:
            print "The specified file cannot be located: " + fileNotPresent.filename
            exit()

        assert self.transcriptdict['pad'] <= 2000, "Padding too large, please use a value below 2000 bases" 

    #Grabs the sequence string from the <sequence/> tagged block
    def grab_element(self, path):
        '''Grabs specific element from the xml file from a provided path'''
        try:
            for item in self.transcriptdict['root'].findall(path):
                result = item.text
            return result
        except:
            print "No sequence was identified"


#Grab exon coords and sequences from the xml file 
    def get_exoncoords(self, genseq):
        ''' Traverses the LRG ETree to find all the useful coordinate values
            and sequence elements.
            Since previous version this has become a dictionary with the 
            following format (as opposed to lists of lists)
            Dict { pad
                   genename
                   refseqname
                   transcripts {  transcript {   protein_seq 
                                                 cds_offset
                                                 exons {  exon_number {   genomic_start
                                                                          genomic_stop
                                                                          transcript_start
                                                                          transcript_stop
                                                                          sequence (with pad)

            This should allow more robust use of the stored values, and enhances          
            transparency of the methods put in place. Absolute references should
            also make the program more easily extensible
        '''
        for items in self.transcriptdict['fixannot'].findall('transcript'):
            t_number = int(items.attrib['name'][1:])    #e.g. 't1', 't2'
            self.transcriptdict['transcripts'][t_number] = {} #first should be indicated with '1'; 'p1' can write on
            self.transcriptdict['transcripts'][t_number]["exons"] = {}
            self.transcriptdict['transcripts'][t_number]['list_of_exons'] = []
            #Gene sequence main coordinates are required to take introns
            #Transcript coordinates wanted for output
            genomic_start = 0
            genomic_end = 0
            transcript_start = 0
            transcript_end = 0
            for exon in items.iter('exon'):
                exon_number = exon.attrib['label']
                self.transcriptdict['transcripts'][t_number]['list_of_exons'].append(exon_number)
                self.transcriptdict['transcripts'][t_number]["exons"][exon_number] = {}
                for coordinates in exon:
                    #Find Transcript Coordinates
                    #if coordinates.attrib['coord_system'][-2] == 't':
                    #    self.transcriptdict['transcripts'][t_number]["exons"][exon_number]['transcript_start'] = int(coordinates.attrib['start'])
                    #    self.transcriptdict['transcripts'][t_number]["exons"][exon_number]['transcript_end'] = int(coordinates.attrib['end'])                   
                    if coordinates.attrib['coord_system'][-2] not in ['t', 'p']:
                        genomic_start = int(coordinates.attrib['start'])
                        genomic_end = int(coordinates.attrib['end'])
                assert genomic_start >= 0, "Exon index out of bounds"
                assert genomic_end <= len(genseq), "Exon index out of bounds"
                seq = genseq[genomic_start-1:genomic_end]
                pad = self.transcriptdict['pad']
                if pad > 0:					
                    assert genomic_start - pad >= 0, "Exon index out of bounds"
                    assert genomic_end + pad <= len(genseq), "Exon index out of bounds"
                    pad5 = genseq[genomic_start-(pad+1):genomic_start-1]
                    pad3 = genseq[genomic_end:genomic_end+(pad+1)]
                    seq = pad5.lower() + seq + pad3.lower()
                    self.transcriptdict['transcripts'][t_number]["exons"][exon_number]['sequence'] = seq
                    self.transcriptdict['transcripts'][t_number]["exons"][exon_number]['genomic_start'] = genomic_start
                    self.transcriptdict['transcripts'][t_number]["exons"][exon_number]['genomic_end'] = genomic_end


    
    def get_protein_exons(self):
        ''' collects full protein sequence for the appropriate transcript '''
        for item in self.transcriptdict['fixannot'].findall('transcript'):
            p_number = int(item.attrib['name'][1:])            
            coding_region = item.find('coding_region')
            coordinates = coding_region.find('coordinates')
            self.transcriptdict['transcripts'][p_number]['cds_offset'] = int(coordinates.attrib['start'])
            
            translation = coding_region.find('translation')
            sequence = translation.find('sequence').text
            self.transcriptdict['transcripts'][p_number]['protein_seq'] = sequence+'* ' # Stop codon


    def find_cds_delay_lrg(self, transcript):
        ''' Method to find the actual start of the translated sequence
            introduced to sort out non-coding exon problems '''
        offset_total = 0
        offset = self.transcriptdict['transcripts'][transcript]['cds_offset']
        for exon in self.transcriptdict['transcripts'][transcript]['list_of_exons']:
            #print 'exon: ' + exon
            #print self.transcriptdict[transcript]['exons'][exon]
            g_start = self.transcriptdict['transcripts'][transcript]['exons'][exon]['genomic_start']
            g_stop = self.transcriptdict['transcripts'][transcript]['exons'][exon]['genomic_end']
            if offset > g_stop :
                offset_total = offset_total + (g_stop - g_start)+1
            elif offset < g_stop and offset > g_start:   
                self.transcriptdict['transcripts'][transcript]['cds_offset'] = offset_total + (offset - g_start)
                break

    def find_cds_delay_gbk(self, transcript):
        ''' Method to find the actual start of the translated sequence
            introduced to sort out non-coding exon problems '''
        offset_total = 0
        offset = self.transcriptdict['transcripts'][transcript]['cds_offset']
        for exon in self.transcriptdict['transcripts'][transcript]['list_of_exons']:
            #print 'exon: ' + exon
            #print self.transcriptdict[transcript]['exons'][exon]
            g_start = self.transcriptdict['transcripts'][transcript]['exons'][exon]['genomic_start']
            g_stop = self.transcriptdict['transcripts'][transcript]['exons'][exon]['genomic_end']
            if offset > g_stop :
                offset_total = offset_total + (g_stop - g_start)
            elif offset < g_stop and offset > g_start:   
                self.transcriptdict['transcripts'][transcript]['cds_offset'] = offset_total + (offset - g_start)
                break
           
                      
    #Character deciding methods for the numbering and amino acid strings
    #May be over-complicating, but separates out logic trees
    def decide_number_string_character(self, char, wait_value, CDS_count,  amino_acid_counter, post_protein_printer, intron_offset, intron_in_padding, protein, intron_out):
        output = ''
        if char.isupper():
            if amino_acid_counter < len(protein):
                if CDS_count % 10 == 1 and wait_value == 0:
                    output = '|'+str(CDS_count)
                    wait_value = len(str(CDS_count))
                    CDS_count = CDS_count + 1
                elif wait_value != 0:
                    CDS_count = CDS_count + 1 
                    wait_value = wait_value - 1
                elif wait_value == 0:
                    output = ' '
                    CDS_count = CDS_count + 1
            elif amino_acid_counter >= len(protein):
                
                if post_protein_printer % 10 == 0 and wait_value == 0:         
                    output = '|+'+str(post_protein_printer+1)
                    #print output
                    wait_value = len(str(post_protein_printer+1))+1
                    post_protein_printer = post_protein_printer + 1
                elif wait_value != 0:
                    wait_value = wait_value -1
                    post_protein_printer = post_protein_printer + 1
                elif wait_value == 0:
                    post_protein_printer = post_protein_printer + 1
                    output = ' '
                    #print 'space'
        else:
            #lower case
            if self.exon_printed == False:
                #intron before exon
                self.dont_print = True
                if intron_offset != 0:
                    intron_offset = intron_offset - 1
                    intron_in_padding = intron_in_padding - 1
                    output = ' '
                elif intron_offset == 0 and intron_in_padding % 5 == 0:
                    output = '.'
                    intron_in_padding = intron_in_padding - 1
                elif intron_offset == 0 and intron_in_padding % 5 != 0:
                    output = ' '
                    intron_in_padding = intron_in_padding - 1
            elif self.exon_printed == True: 
                #intron after exon
                if wait_value != 0:
                    wait_value = wait_value - 1
                    intron_out = intron_out + 1  
                elif wait_value == 0:
                    if intron_out % 5 == 4:
                        output = '.'
                        intron_out = intron_out + 1
                    elif intron_out % 5 != 4:
                        output = ' '
                        intron_out = intron_out + 1
                   
        return (output, wait_value, CDS_count,  amino_acid_counter, post_protein_printer, intron_offset, intron_in_padding, intron_out)


    def decide_amino_string_character(self, char, codon_count, amino_acid_counter, codon_numbered, protein):
        output = ''
        if char.isupper() and amino_acid_counter < len(protein):## Bug, condition added
            if self.amino_printing == True:
                self.amino_spacing = True
                if codon_count == 3:
                    #print 'AA = ' + protein[amino_acid_counter:amino_acid_counter+1][0]
                    output = protein[amino_acid_counter:amino_acid_counter+1][0]
                    #print output
                    amino_acid_counter = amino_acid_counter + 1                     
                    codon_numbered = False
                    codon_count = 1
                else:
                    codon_count = codon_count + 1
                    output = ' '
            elif self.amino_printing == False:
                output = ' '
        elif char.islower(): 
            output = ' ' 
        
        return (output, codon_count, amino_acid_counter, codon_numbered)
    
    def decide_amino_number_string_character(self, char, amino_wait, codon_numbered,  amino_acid_counter):
        output = ''
        if amino_wait != 0:
            amino_wait = amino_wait - 1
        elif amino_wait == 0:
            if amino_acid_counter % 10 == 1:
                if codon_numbered == False:
                    output = '|'+str(amino_acid_counter)
                    amino_wait = len(str(amino_acid_counter))
                    codon_numbered = True
                elif codon_numbered == True:
                    #NOT SURE - condition shouldn't occur
                    output = ' '
            elif amino_acid_counter %10 != 1:
                output = ' '
        return (output, amino_wait, codon_numbered, amino_acid_counter)


    def print_latex_header(self, outfile, refseqid):
        self.line_printer('\\documentclass{article}', outfile)
        self.line_printer('\\usepackage{fancyvrb}', outfile)
        self.line_printer('\\begin{document}', outfile)
        self.line_printer('\\renewcommand{\\footrulewidth}{1pt}', outfile)
        self.line_printer('\\renewcommand{\\headrulewidth}{0pt}', outfile)
        self.line_printer('\\begin{center}', outfile)        
        self.line_printer('\\begin{large}', outfile)
        self.line_printer(' Gene: %s - Sequence: %s' % (self.transcriptdict['genename'], refseqid), outfile)
        self.line_printer(' ', outfile)
        self.line_printer(' Date : \\today\\\\\\\\', outfile)
        self.line_printer('\\end{large}', outfile)
        self.line_printer('\\end{center}', outfile)
        self.line_printer('$1^{st}$ line: Base numbering. Full stops for intronic +/- 5, 10, 15...\\\\', outfile)
        self.line_printer('$2^{nd}$ line: Base sequence. lower case Introns, upper case Exons\\\\', outfile)
        self.line_printer('$3^{rd}$ line: Amino acid sequence. Printed on FIRST base of codon\\\\', outfile)
        self.line_printer('$4^{th}$ line: Amino acid numbering. Numbered on $1^{st}$ and increments of 10\\\\', outfile)
        self.line_printer(' \\begin{Verbatim}', outfile)


    def print_latex(self, transcript, outfile):
        latex_dict = self.transcriptdict['transcripts'][transcript]
        ''' Creates a LaTex file which can be converted to a final document
            Lengths of numbers calculated using len(#)'''
            
        protein = latex_dict['protein_seq']
        #print protein
        refseqid = self.transcriptdict['refseqname'].replace('_', '\_')#Required for LaTex
        CDS_count = 1 - latex_dict['cds_offset'] #A variable to keep a count of the 
                                                 #transcript length across all exons
	    #The initial line(s) of the LaTex file, required to execute
	    
        self.print_latex_header(outfile, refseqid)

        wait_value = 0
        codon_count = 3         #Print on first codon
        amino_acid_counter = 0
        amino_wait = 0
        amino_printing = False
        codon_numbered = False
        post_protein_printer = 0
        next_number_string = '' 
        for exon in latex_dict['list_of_exons']:
            intron_offset = self.transcriptdict['pad_offset']
            intron_in_padding = self.transcriptdict['pad']
            intron_out = 0 ## Or 0?
            self.exon_printed = False
            number_string  = [] 
            dna_string = []
            amino_string = []
            amino_number_string = []
            self.amino_spacing = False
            self.exon_spacing = False
            exon_dict = latex_dict['exons'][exon]
            ex_start = exon_dict['genomic_start']
            ex_end = exon_dict['genomic_end']
            self.line_printer(' ', outfile)
            self.line_printer('Exon %s | Start: %s | End: %s | Length: %s' % 
                (exon, str(ex_start), str(ex_end), str(ex_end - ex_start)), outfile)
            sequence = exon_dict['sequence']

            line_count = 0

            for char in sequence:
                #Stop each line at a specific length
                #Remainder method prevents count being 
                #print amino_acid_counter
                if line_count % 60 == 0:
                    wait_value = 0
                    amino_wait = 0
                    self.line_printer(number_string, outfile)
                    self.line_printer(dna_string, outfile)
                    if self.amino_spacing == True: self.line_printer(amino_string, outfile)
                    self.line_printer(amino_number_string, outfile)
                    if self.amino_spacing == True: self.line_printer('  ', outfile)
                    amino_string = []
                    number_string = []
                    dna_string = []
                    amino_number_string = []
                    self.exon_spacing = False
                    self.amino_spacing = False
                    
                dna_string.append(char)
                
                if char.isupper() : self.exon_printed = True
                if CDS_count == 1: self.amino_printing = True
                if amino_acid_counter >= len(protein): self.amino_printing = False
                    
                #Calls specific methods for character decision
                #Simplifies local logic                
                (next_amino_string, codon_count, amino_acid_counter, codon_numbered) = self.decide_amino_string_character(char, codon_count, amino_acid_counter, codon_numbered, protein)  
                amino_string.append(next_amino_string)

                (next_amino_number, amino_wait, codon_numbered, amino_acid_counter) = self.decide_amino_number_string_character(char, amino_wait, codon_numbered,  amino_acid_counter)
                amino_number_string.append(next_amino_number)
                
                (next_number_string, wait_value, CDS_count, amino_acid_counter, post_protein_printer, intron_offset, intron_in_padding, intron_out) = self.decide_number_string_character(char, wait_value, CDS_count, amino_acid_counter, post_protein_printer, intron_offset, intron_in_padding, protein, intron_out)
                number_string.append(next_number_string)

                line_count = line_count + 1
                
            
            #Section for incomplete lines (has not reached line-limit print)
            #Called after exon finishes printing bases
            if len(dna_string) != 0:
                wait_value = 0
                amino_wait = 0
                self.line_printer(number_string, outfile)
                self.line_printer(dna_string, outfile)
                if self.amino_spacing == False: self.line_printer(amino_string, outfile)
                self.line_printer(amino_number_string, outfile)
                if self.amino_spacing == True: self.line_printer('  ', outfile)
                
        self.print_latex_footer(outfile)
        
    def print_latex_footer(self, outfile):
        self.line_printer('\\end{Verbatim}', outfile)       
        self.line_printer('\\end{document}', outfile)

    def line_printer(self, string, outfile):
        print >>outfile, ''.join(string)

    def examine_gbk(self):
        dictionary = self.transcriptdict['input'][self.transcriptdict['refseqname']]
        self.transcriptdict['full genomic sequence'] = dictionary.seq
        features = dictionary.features
        exons = []
        cds = []
        #Sort through SeqFeatures to find the good stuff
        for feature in features:
            if feature.type == 'exon':
                exons.append(feature)
            elif feature.type == 'CDS':
                cds.append(feature)
        self.transcriptdict['genename'] = exons[0].qualifiers['gene'][0]
        self.gbk_protein(cds)
        self.exons_gbk(exons)
        self.transcriptdict['transcripts'][1]['cds_offset'] = cds[0].location.start
        self.find_cds_delay_gbk(1)
        
    def gbk_protein(self, cds):
        if len(cds) > 1 : print "This gene has multiple transcripts, sort it out!"
        for x in cds:
            protein_sequence = x.qualifiers['translation'][0] + '* '
            #print protein_sequence
            self.transcriptdict['transcripts'][1]['protein_seq'] = protein_sequence

    def exons_gbk(self, exons):
        self.transcriptdict['transcripts'][1]['list_of_exons'] = []
        exon_count = 1
        exon_number = 0
        for x in exons:
            #Some Genbank files do not feature explicitly numbered exons
            if 'number' in x.qualifiers:
                exon_number = x.qualifiers['number'][0]
            else:
                exon_number = str(exon_count)
                exon_count = exon_count + 1
            self.transcriptdict['transcripts'][1]['exons'][exon_number] = {}
            self.transcriptdict['transcripts'][1]['list_of_exons'].append(exon_number)
            location_feature = x.location
            self.transcriptdict['transcripts'][1]['exons'][exon_number]['genomic_start'] = location_feature.start
            self.transcriptdict['transcripts'][1]['exons'][exon_number]['genomic_end'] = location_feature.end
            sequence = self.transcriptdict['full genomic sequence'][location_feature.start:location_feature.end]
            if self.transcriptdict['pad'] !=0:
                pad = self.transcriptdict['pad']
                pad5 = self.transcriptdict['full genomic sequence'][location_feature.start-(pad+1):location_feature.start-1]
                pad3 = self.transcriptdict['full genomic sequence'][location_feature.end:location_feature.end+(pad+1)]
                #print exon_number + ' : pad3 : ' + pad3
                sequence = pad5.lower() + sequence + pad3.lower()
            self.transcriptdict['transcripts'][1]['exons'][exon_number]['sequence'] = sequence


            
    def run(self):
        
        #initial sequence grabbing and populating dictionaries
        if self.file_type == 'lrg':
            gen_seq = self.grab_element('fixed_annotation/sequence')
            self.get_exoncoords(gen_seq)
            self.get_protein_exons()
            for transcript in self.transcriptdict['transcripts'].keys():
                #print 'transcript: ' + str(transcript)
                #print self.transcriptdict['transcripts'][transcript]
                self.transcriptdict['transcripts'][transcript]['list_of_exons'].sort(key=float)
                self.find_cds_delay_lrg(transcript)
        elif self.file_type == 'gbk':
            #This bit
            self.examine_gbk()

        for entry in self.transcriptdict['transcripts'].keys():
            outputfile = self.transcriptdict['genename'] +'_'+self.fileName.split('.')[0]+'_'+str(entry)+"_"+str(self.transcriptdict['pad'])
            outputfilename = outputfile + '.tex'
            outputFilePath = os.path.join('outputFiles', outputfilename)
            if outputfile in self.existingFiles:
            #tests whether file already exists
                print 'The output file already exists in the present directory'
                print 'Would you like to overwrite the file? y/n'
                c = 0
                while c == 0:
                    userChoice = raw_input('> ')
                    if userChoice == 'n':
                        print "Program exited without creating file"
                        exit() # can change later to offer alternate filename
                    elif userChoice == 'y':
                        c += 1
                    else:
                        print "Invalid selection please type y or n"
            out = open(outputFilePath, "w")
            self.print_latex(entry, out)
            return outputfilename
