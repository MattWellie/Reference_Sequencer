#Complete overhaul of original version
import sys
import xml.etree.ElementTree as etree
import os

class Parser:

    '''
    Class version: 0.1
    Modified Date: 10/01/2015
    Author : Matt Welland
    
    Notes:
        Majority of variable storage change to dictionary entries
        -   This replaces the list storage of initial draft
        Checked with clinical scientists, .gbk variant required
    '''

    def __init__(self, file_name, padding, existingfiles):#, root, option):
        self.fileName = file_name
        #Read in the specified input file into a variable
        try:
            self.transcriptdict = {}
            self.tree = etree.parse(self.fileName)
            self.root = self.tree.getroot()
            self.fixannot = self.root.find('fixed_annotation') #ensures only exons from the fixed annotation will be taken
            self.transcriptdict['genename'] = self.root.find('updatable_annotation/annotation_set/lrg_locus').text    
            self.transcriptdict['refseqname'] = self.root.find('fixed_annotation/sequence_source').text
            self.existingFiles = existingfiles
            self.transcriptdict['pad'] = int(padding)
            self.transcriptdict['pad_offset'] = padding % 5
            self.is_matt_awesome = True
        except IOError as fileNotPresent:
            print "The specified file cannot be located: " + fileNotPresent.filename
            exit()

        assert self.transcriptdict['pad'] <= 2000, "Padding too large, please use a value below 2000 bases" 

    #Check the version of the file we are opening is correct
        if self.root.attrib['schema_version'] <> '1.9':
            print 'This LRG file is not the correct version for this script'
            print 'This is designed for v.1.8'
            print 'This file is v.' + self.root.attrib['schema_version']

    #Grabs the sequence string from the <sequence/> tagged block
    def grab_element(self, path, root):
        '''Grabs specific element from the xml file from a provided path'''
        try:
            for item in self.root.findall(path):
                result = item.text
            return result
        except:
            print "No sequence was identified"


#Grab exon coords and sequences from the xml file 
    def get_exoncoords(self, level, genseq):
        ''' Traverses the LRG ETree to find all the useful coordinate values
            and sequence elements.
            Since previous version this has become a dictionary with the 
            following format (as opposed to lists of lists)
            Dict { pad
                   genename
                   refseqname
                   transcript {   protein_seq 
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
        for items in level.findall('transcript'):
            t_number = int(items.attrib['name'][1:])    #e.g. 't1', 't2'
            self.transcriptdict[t_number] = {} #first should be indicated with '1'; 'p1' can write on
            self.transcriptdict[t_number]["exons"] = {}
            self.transcriptdict[t_number]['list_of_exons'] = []
            #Gene sequence main coordinates are required to take introns
            #Transcript coordinates wanted for output
            genomic_start = 0
            genomic_end = 0
            transcript_start = 0
            transcript_end = 0
            for exon in items.iter('exon'):
                exon_number = exon.attrib['label']
                self.transcriptdict[t_number]['list_of_exons'].append(exon_number)
                self.transcriptdict[t_number]["exons"][exon_number] = {}
                for coordinates in exon:
                    #Find Transcript Coordinates
                    if coordinates.attrib['coord_system'][-2] == 't':
                        self.transcriptdict[t_number]["exons"][exon_number]['transcript_start'] = int(coordinates.attrib['start'])
                        self.transcriptdict[t_number]["exons"][exon_number]['transcript_end'] = int(coordinates.attrib['end'])                   
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
                    pad5 = genseq[genomic_start-pad:genomic_start]
                    pad3 = genseq[genomic_end:genomic_end+pad]
                    seq = pad5.lower() + seq + pad3.lower()
                    self.transcriptdict[t_number]["exons"][exon_number]['sequence'] = seq
                    self.transcriptdict[t_number]["exons"][exon_number]['genomic_start'] = genomic_start
                    self.transcriptdict[t_number]["exons"][exon_number]['genomic_end'] = genomic_end


    
    def get_protein_exons(self, prot_level):
        ''' collects full protein sequence for the appropriate transcript '''
        for item in prot_level.findall('transcript'):
            p_number = int(item.attrib['name'][1:])            
            coding_region = item.find('coding_region')
            coordinates = coding_region.find('coordinates')
            self.transcriptdict[p_number]['cds_offset'] = int(coordinates.attrib['start'])
            
            translation = coding_region.find('translation')
            sequence = translation.find('sequence').text
            self.transcriptdict[p_number]['protein_seq'] = sequence+'* ' # Stop codon


    def find_cds_delay(self, transcript):
        ''' Method to find the actual start of the translated sequence
            introduced to sort out non-coding exon problems '''
        offset_found = False
        offset_total = 0
        offset = self.transcriptdict[transcript]['cds_offset']
        for exon in self.transcriptdict[transcript]['list_of_exons']:
            #print 'exon: ' + exon
            #print self.transcriptdict[transcript]['exons'][exon]
            g_start = self.transcriptdict[transcript]['exons'][exon]['genomic_start']
            g_stop = self.transcriptdict[transcript]['exons'][exon]['genomic_end']
            if offset > g_stop and offset_found == False:
                offset_total = offset_total + (g_stop - g_start)+1
            elif offset < g_stop and offset > g_start:   
                offset_total = offset_total + (offset - g_start)
                offset_found = True
            self.transcriptdict[transcript]['cds_offset'] = offset_total
            

    def print_latex(self, transcript, outfile):
        latex_dict = self.transcriptdict[transcript]
        ''' Creates a LaTex readable file which can be converted to a final document
	        Currently only working for DNA sequences
            Lengths of numbers calculated using len(###)'''
        protein = latex_dict['protein_seq']
        refseqid = self.transcriptdict['refseqname'].replace('_', '\_')#Required for LaTex
        CDS_count = 1 - latex_dict['cds_offset'] #A variable to keep a count of the 
                                                 #transcript length across all exons

	    #The initial line(s) of the LaTex file, required to run
        self.line_printer('\\documentclass{article}', outfile)
        self.line_printer('\\usepackage{fancyvrb}', outfile)
        self.line_printer('\\begin{document}', outfile)
        self.line_printer('\\begin{center}', outfile)        
        self.line_printer('\\begin{large}', outfile)
        self.line_printer(' Gene: %s - Sequence: %s' % (self.transcriptdict['genename'], refseqid), outfile)
        self.line_printer(' ', outfile)
        self.line_printer(' Date : \\today', outfile)
        self.line_printer('\\end{large}', outfile)
        self.line_printer('\\end{center}', outfile)
        self.line_printer(' \\begin{Verbatim}', outfile)

        wait_value = 0
        codon_count = 3         #Print on first codon
        amino_acid_counter = 0
        amino_wait = 0
        amino_printing = False
        codon_numbered = False
        post_protein_printer = 1
        for exon in latex_dict['list_of_exons']:
            intron_offset = self.pad_offset
            intron_wait = 3
            intron_in_padding = self.pad
            intron_out_padding = self.pad
            exon_printed = False
            number_string  = [] 
            dna_string = []
            amino_string = []
            amino_number_string = []
            amino_spacing = False
            exon_spacing = False
            dont_print = False
            exon_dict = latex_dict['exons'][exon]
            tran_start = exon_dict['transcript_start']
            tran_end = exon_dict['transcript_end']
            sequence = exon_dict['sequence']
            self.line_printer(' ', outfile)
            self.line_printer('Exon %s | Start: %s | End: %s | Length: %s' % 
                (exon, str(tran_start), str(tran_end), str(tran_end - tran_start)), outfile)
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
                    if amino_spacing == True: self.line_printer(amino_string, outfile)
                    self.line_printer(amino_number_string, outfile)
                    if amino_spacing == True: self.line_printer('  ', outfile)
                    amino_string = []
                    number_string = []
                    dna_string = []
                    amino_number_string = []
                    exon_spacing = False
                    amino_spacing = False
                dna_string.append(char)
                if char.isupper() : 
                    exon_printed = True # Can use same variable as above.
                                
                if CDS_count == 1:
                    amino_printing = True
                if amino_acid_counter >= len(protein):
                    amino_printing = False

                #Intron numbering
                #exon_printed == false means intron padding before exon
                if char.islower() and exon_printed == False:
                    dont_print = True
                    if intron_offset != 0:
                        intron_offset = intron_offset - 1
                        intron_in_padding = intron_in_padding - 1
                        number_string.append(' ')
                    elif intron_offset == 0 and intron_in_padding % 5 == 0:
                        number_string.append('.')
                        intron_in_padding = intron_in_padding - 1
                    elif intron_offset == 0 and intron_in_padding % 5 != 0:
                        number_string.append(' ')
                        intron_in_padding = intron_in_padding - 1

                                   
                if amino_printing == True and char.isupper():
                    amino_spacing = True
                    if codon_count == 3:
                        amino_string.append(protein[amino_acid_counter])
                        amino_acid_counter = amino_acid_counter + 1
                        codon_numbered = False
                        codon_count = 1
                    else:
                        codon_count = codon_count + 1
                        amino_string.append(' ')
                else:
                    amino_string.append(' ') 
                
                if char.isupper() and amino_acid_counter < len(protein):
                    if CDS_count % 10 == 1 and wait_value == 0:
                        number_string.append('|'+str(CDS_count))
                        wait_value = len(str(CDS_count))
                        CDS_count = CDS_count + 1
                    elif wait_value != 0:
                        CDS_count = CDS_count + 1 
                        wait_value = wait_value - 1
                    else:
                        number_string.append(' ')
                        CDS_count = CDS_count + 1   
                elif char.isupper() and amino_acid_counter >= len(protein):
                    if post_protein_printer % 10 == 1 and wait_value == 0:  
                        number_string.append('|+'+str(post_protein_printer))
                        wait_value = len(str(post_protein_printer))+1
                        post_protein_printer = post_protein_printer + 1
                    elif wait_value != 0:
                        wait_value = wait_value -1
                        post_protein_printer = post_protein_printer + 1
                    else:
                        post_protein_printer = post_protein_printer + 1
                        number_string.append(' ')
                
                #Intron after exon
                if char.islower() and wait_value == 0 and exon_printed == True and intron_wait == 0:
                    dont_print = True
                    if intron_out_padding % 5 == 0:
                        number_string.append('.')
                        intron_out_padding = intron_out_padding - 1
                    elif intron_out_padding % 5 != 0:
                        number_string.append(' ')
                        intron_out_padding = intron_out_padding - 1
                elif char.islower() and wait_value == 0 and exon_printed == True:
                    dont_print = True
                    number_string.append(' ')
                    intron_out_padding = intron_out_padding - 1
                    intron_wait = intron_wait - 1 
                 

                else:
                    if wait_value != 0:
                        wait_value = wait_value - 1
                    elif dont_print == True:
                        dont_print = False
                    else:
                        number_string.append(' ')
                
                #Amino Acid numbering
                if amino_acid_counter %10 == 1 and codon_numbered == False:
                    amino_number_string.append('|'+str(amino_acid_counter))
                    amino_wait = len(str(amino_acid_counter))
                    codon_numbered = True
                elif amino_wait != 0:
                    amino_wait = amino_wait - 1
                elif amino_acid_counter %10 != 1 and amino_wait == 0:
                    amino_number_string.append(' ')
                line_count += 1
            
            #Section for incomplete lines (has not reached line-limit print)
            if len(dna_string) != 0:
                wait_value = 0
                amino_wait = 0
                self.line_printer(number_string, outfile)
                self.line_printer(dna_string, outfile)
                if amino_spacing == False: self.line_printer(amino_string, outfile)
                self.line_printer(amino_number_string, outfile)
                if amino_spacing == True: self.line_printer('  ', outfile)

        self.line_printer('\\end{Verbatim}', outfile)       
        self.line_printer('\\end{document}', outfile)

    def line_printer(self, string, outfile):
        print >>outfile, ''.join(string)

    def run(self):
        
        #initial sequence grabbing and populating dictionaries
        gen_seq = self.grab_element('fixed_annotation/sequence', self.root)
        self.get_exoncoords(self.fixannot, gen_seq)
        self.get_protein_exons(self.fixannot)
        for transcript in self.transcriptdict.keys():
            self.transcriptdict[transcript]['list_of_exons'].sort(key=float)
            #print self.transcriptdict[transcript]['list_of_exons']
            self.find_cds_delay(transcript)

        for entry in self.transcriptdict.keys():
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
