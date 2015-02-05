from xml.etree.ElementTree import parse


class LrgParser:

    """
    Class version: 0.2
    Modified Date: 04/02/2015
    Author : Matt Welland

    Notes:
        Isolated class to deal exclusively with LRG files
        Should return dictionary, not write full output

    Parses the input file to find all the useful values
    This will populate a dictionary to be returned at completion

            Dict { pad
                   filename
                   genename
                   refseqname
                   transcripts {  transcript {   protein_seq
                                                 cds_offset
                                                 exons {  exon_number {   genomic_start
                                                                          genomic_stop
                                                                          transcript_start
                                                                          transcript_stop
                                                                          sequence (with pad)
    """

    def __init__(self, file_name, padding):
        self.fileName = file_name
        # Read in the specified input file into a variable
        try:
            self.tree = parse(self.fileName)
            self.transcriptdict = {'transcripts': {},
                                   'root': self.tree.getroot(),
                                   'pad': int(padding),
                                   'pad_offset': int(padding) % 5}
            self.transcriptdict['fixannot'] = self.transcriptdict['root'].find(
                'fixed_annotation')  # ensures only exons from the fixed annotation will be taken
            self.transcriptdict['genename'] = self.transcriptdict['root'].find(
                'updatable_annotation/annotation_set/lrg_locus').text
            self.transcriptdict['refseqname'] = self.transcriptdict['root'].find(
                'fixed_annotation/sequence_source').text
            self.transcriptdict['filename'] = self.transcriptdict['genename'] + '_' + self.fileName.split('.')[
                0] + '_' + str(padding)

            if self.transcriptdict['root'].attrib['schema_version'] != '1.9':
                print 'This LRG file is not the correct version for this script'
                print 'This is designed for v.1.8'
                print 'This file is v.' + self.root.attrib['schema_version']
            self.is_matt_awesome = True
        except IOError as fileNotPresent:
            print "The specified file cannot be located: " + fileNotPresent.filename
            exit()

        # This assertion is an artifact from LRG parsing, will need to be updated
        assert self.transcriptdict['pad'] <= 2000, "Padding too large, please use a value below 2000 bases"
        assert self.transcriptdict['pad'] >= 0, "Padding must be 0 or a positive value"
	
        if self.transcriptdict['pad'] < 0:
            exit()

    # Grabs the sequence string from the <sequence/> tagged block
    def grab_element(self, path):
        """ Grabs specific element from the xml file from a provided path """
        try:
            for item in self.transcriptdict['root'].findall(path):
                result = item.text
            return result
        except:
            print "No sequence was identified"
			

    # Grab exon coords from the file - separated from sequence gathering
    def get_exon_coords(self):
        '''
        :return:
        '''
        """ Traverses the LRG ETree to find all the useful values
            This should allow more robust use of the stored values, and enhances
            transparency of the methods put in place. Absolute references should
            also make the program more easily extensible
        """

        for items in self.transcriptdict['fixannot'].findall('transcript'):
            t_number = int(items.attrib['name'][1:])  # e.g. 't1', 't2'
            # print 't_number: ' + str(t_number)
            self.transcriptdict['transcripts'][t_number] = {}  # First should be indicated with '1'; 'p1' can write on
            self.transcriptdict['transcripts'][t_number]["exons"] = {}
            self.transcriptdict['transcripts'][t_number]['list_of_exons'] = []
            # Gene sequence main coordinates are required to take introns
            # Transcript coordinates wanted for output  
            genomic_start = 0
            genomic_end = 0
            transcript_start = 0
            transcript_end = 0
            for exon in items.iter('exon'):
                exon_number = exon.attrib['label']
                self.transcriptdict['transcripts'][t_number]['list_of_exons'].append(exon_number)
                self.transcriptdict['transcripts'][t_number]["exons"][exon_number] = {}
                for coordinates in exon:
                    if coordinates.attrib['coord_system'][-2] not in ['t', 'p']:
                        genomic_start = int(coordinates.attrib['start'])
                        genomic_end = int(coordinates.attrib['end'])
                assert genomic_start >= 0, "Exon index out of bounds"
                self.transcriptdict['transcripts'][t_number]["exons"][exon_number]['genomic_start'] = genomic_start
                self.transcriptdict['transcripts'][t_number]["exons"][exon_number]['genomic_end'] = genomic_end

    def grab_exon_contents(self, genseq):
        transcripts = self.transcriptdict['transcripts'].keys()
        for transcript in transcripts:
            exon_list = self.transcriptdict['transcripts'][transcript]['list_of_exons']
            for exon_number in exon_list:
                genomic_start = self.transcriptdict['transcripts'][transcript]['exons'][exon_number]['genomic_start']
                genomic_end = self.transcriptdict['transcripts'][transcript]['exons'][exon_number]['genomic_end']
                seq = genseq[genomic_start - 1:genomic_end]
                pad = self.transcriptdict['pad']
                if pad > 0:
                    assert genomic_start - pad >= 0, "Exon index out of bounds"
                    assert genomic_end + pad <= len(genseq), "Exon index out of bounds"
                    pad5 = genseq[genomic_start - (pad + 1):genomic_start - 1]
                    pad3 = genseq[genomic_end:genomic_end + (pad + 1)]
                    seq = pad5.lower() + seq + pad3.lower()
                self.transcriptdict['transcripts'][transcript]["exons"][exon_number]['sequence'] = seq

    def get_protein_exons(self):
        """ Collects full protein sequence for the appropriate transcript """
        for item in self.transcriptdict['fixannot'].findall('transcript'):
            p_number = int(item.attrib['name'][1:])
            coding_region = item.find('coding_region')
            coordinates = coding_region.find('coordinates')
            self.transcriptdict['transcripts'][p_number]['cds_offset'] = int(coordinates.attrib['start'])
            translation = coding_region.find('translation')
            sequence = translation.find('sequence').text
            self.transcriptdict['transcripts'][p_number]['protein_seq'] = sequence + '* '  # Stop codon

    def find_cds_delay(self, transcript):
        """ Method to find the actual start of the translated sequence
            introduced to sort out non-coding exon problems """
        offset_total = 0
        offset = self.transcriptdict['transcripts'][transcript]['cds_offset']
        for exon in self.transcriptdict['transcripts'][transcript]['list_of_exons']:
            g_start = self.transcriptdict['transcripts'][transcript]['exons'][exon]['genomic_start']
            g_stop = self.transcriptdict['transcripts'][transcript]['exons'][exon]['genomic_end']
            if offset > g_stop:
                offset_total = offset_total + (g_stop - g_start) + 1
            elif offset < g_stop and offset > g_start:
                self.transcriptdict['transcripts'][transcript]['cds_offset'] = offset_total + (offset - g_start)
                break

    def run(self):

        # Initial sequence grabbing and populating dictionaries
        gen_seq = self.grab_element('fixed_annotation/sequence')
        self.get_exon_coords()
        self.grab_exon_contents(gen_seq)
        self.get_protein_exons()
        for transcript in self.transcriptdict['transcripts'].keys():
            self.transcriptdict['transcripts'][transcript]['list_of_exons'].sort(key=float)
            self.find_cds_delay(transcript)

        return self.transcriptdict
