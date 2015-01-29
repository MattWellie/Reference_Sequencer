''' This is the Reader class which uses the completed dictionary
    from the Parser classes as input and create a list object
    containing each of the lines to be used as output in the
    appropriate order to be printed.

    Partitioning the output process will allow the program to be
    able to output to a simple .txt format or to a LaTex document
    with appropriate headers and formatting
    This will also allow the output to be formally tested or a
    variety of assertions to be performed before attempting to
    generate output'''


class Reader:
    '''
    Class version = 0.1
    Author = Matt Welland
    Date = 29-01-2014

    This class is used to create list object which will contain the lines
    to be printed to a final output file

    This separates the creation of the dictionary, the writing of the
    output and the actual creation of the output file
    '''

    def __init__(self, transcriptdict, transcript, write_as_LaTex):
        self.transcriptdict = transcriptdict
        self.write_as_LaTex = write_as_LaTex
        self.transcript = transcript
        self.output_list = []
        self.amino_printing = False
        self.amino_spacing = False
        self.exon_spacing = False
        self.exon_printed = False
        self.dont_print = False

    def decide_number_string_character(self, char, wait_value, cds_count, amino_acid_counter, post_protein_printer,
                                       intron_offset, intron_in_padding, protein_length, intron_out):
        '''
        :param char: the next base character to be written
        :param wait_value: variable indicating whether a number has already been written
        :param cds_count: the CDS position of the current char/base
        :param amino_acid_counter: position of the amino acid in the protein sequence
        :param post_protein_printer: to indicate the position of the exon after stop codon
        :param intron_offset:
        :param intron_in_padding:
        :param protein_length: length of protein sequence
        :param intron_out:
        :return: all input values complete with appropriate additions and subtractions, and
                 the new character(s) to be added to the number string

        This function is responsible for determining the next value(s) to be added to the
        output string which will appear above the base sequence.
        '''

        output = ''
        if char.isupper():
            # Upper case
            if amino_acid_counter < protein_length:
                if cds_count % 10 == 1 and wait_value == 0:
                    output = '|' + str(cds_count)
                    wait_value = len(str(cds_count))
                    cds_count += 1
                elif wait_value != 0:
                    cds_count += 1
                    wait_value -= 1
                elif wait_value == 0:
                    output = ' '
                    cds_count += 1
            elif amino_acid_counter >= protein_length:

                if post_protein_printer % 10 == 0 and wait_value == 0:
                    output = '|+' + str(post_protein_printer + 1)
                    wait_value = len(str(post_protein_printer + 1)) + 1
                    post_protein_printer += 1
                elif wait_value != 0:
                    wait_value -= 1
                    post_protein_printer += 1
                elif wait_value == 0:
                    post_protein_printer += 1
                    output = ' '
                    # print 'space'
        else:
            # Lower case
            if not self.exon_printed:
                # Intron before exon
                self.dont_print = True
                if intron_offset != 0:
                    intron_offset -= 1
                    intron_in_padding -= 1
                    output = ' '
                elif intron_offset == 0 and intron_in_padding % 5 == 0:
                    output = '.'
                    intron_in_padding -= 1
                elif intron_offset == 0 and intron_in_padding % 5 != 0:
                    output = ' '
                    intron_in_padding -= 1
            elif self.exon_printed:
                # Intron after exon
                if wait_value != 0:
                    wait_value -= 1
                    intron_out += 1
                elif wait_value == 0:
                    if intron_out % 5 == 4:
                        output = '.'
                        intron_out += 1
                    elif intron_out % 5 != 4:
                        output = ' '
                        intron_out += 1

        return (output, wait_value, cds_count, amino_acid_counter,
                post_protein_printer, intron_offset, intron_in_padding,intron_out)

    def decide_amino_string_character(self, char, codon_count, amino_acid_counter, codon_numbered, protein):
        '''
        :param char: the next base character to be written
        :param codon_count: the position of the current base within the reading frame
        :param amino_acid_counter: the position of the current AA in the protein sequence
        :param codon_numbered: Boolean; has the current codon been numbered
        :param protein: the full protein sequence
        :return: all input values complete with appropriate additions and subtractions, and
                 the new character(s) to be added to the amino number string

        This function determines the next character to be added to the string which shows
        the numbering for the amino acid labelling line
        '''

        output = ''
        if char.isupper() and amino_acid_counter < len(protein):  # Bug, condition added
            if self.amino_printing:
                self.amino_spacing = True
                if codon_count == 3:
                    # print 'AA = ' + protein[amino_acid_counter:amino_acid_counter+1][0]
                    output = protein[amino_acid_counter:amino_acid_counter + 1][0]
                    amino_acid_counter += 1
                    codon_numbered = False
                    codon_count = 1
                else:
                    codon_count += 1
                    output = ' '
            elif not self.amino_printing:
                output = ' '
        elif char.islower():
            output = ' '

        return output, codon_count, amino_acid_counter, codon_numbered

    def print_latex_header(self, refseqid):
        '''
        :param refseqid: reference sequence identifier for current input

        This function can be called if the file to be written out is designed to be
        executed as a LaTex script. This will insert the appropriate preamble to
        allow an article class document to be produced which uses a verbatim output
        operation
        '''

        self.line_printer('\\documentclass{article}')
        self.line_printer('\\usepackage{fancyvrb}')
        self.line_printer('\\begin{document}')
        self.line_printer('\\renewcommand{\\footrulewidth}{1pt}')
        self.line_printer('\\renewcommand{\\headrulewidth}{0pt}')
        self.line_printer('\\begin{center}')
        self.line_printer('\\begin{large}')
        self.line_printer(' Gene: %s - Sequence: %s' % (self.transcriptdict['genename'], refseqid))
        self.line_printer(' ')
        self.line_printer(' Date : \\today\\\\\\\\')
        self.line_printer('\\end{large}')
        self.line_printer('\\end{center}')
        self.line_printer('$1^{st}$ line: Base numbering. Full stops for intronic +/- 5, 10, 15...\\\\')
        self.line_printer('$2^{nd}$ line: Base sequence. lower case Introns, upper case Exons\\\\')
        self.line_printer('$3^{rd}$ line: Amino acid sequence. Printed on FIRST base of codon\\\\')
        self.line_printer('$4^{th}$ line: Amino acid numbering. Numbered on $1^{st}$ and increments of 10\\\\')
        self.line_printer(' \\begin{Verbatim}')

    def print_latex(self):

        '''
        This large class imports the entire dictionary and scans through the input dictionary
        to build the output. This output will be kept as a list of strings (with the appropriate
        order maintained) to allow a later decision on whether to print to LaTex, txt or other.
        '''

        latex_dict = self.transcriptdict['transcripts'][self.transcript]
        ''' Creates a LaTex file which can be converted to a final document
            Lengths of numbers calculated using len(#)'''

        protein = latex_dict['protein_seq']
        refseqid = self.transcriptdict['refseqname'].replace('_', '\_')  # Required for LaTex
        assert isinstance(latex_dict, object)
        cds_count = 1 - latex_dict['cds_offset']  # A variable to keep a count of the
        # transcript length across all exons
        # Account for the number 0 being skipped
        cds_count -= 1
        # The CDS begins at one, the preceeding base is -1. There is no 0
        # The writer must skip 0, so the extra length compensates to keep
        # values in the correct places

        # The initial line(s) of the LaTex file, required to execute
        if self.write_as_LaTex:
            self.print_latex_header(refseqid)

        wait_value = 0
        codon_count = 3  # Print on first codon
        amino_acid_counter = 0
        amino_wait = 0
        codon_numbered = False
        post_protein_printer = 0
        for exon in latex_dict['list_of_exons']:
            intron_offset = self.transcriptdict['pad_offset']
            intron_in_padding = self.transcriptdict['pad']
            intron_out = 0  # Or 0?
            self.exon_printed = False
            number_string = []
            dna_string = []
            amino_string = []
            amino_number_string = []
            self.amino_spacing = False
            self.exon_spacing = False
            exon_dict = latex_dict['exons'][exon]
            ex_start = exon_dict['genomic_start']
            ex_end = exon_dict['genomic_end']
            self.line_printer(' ')
            self.line_printer('Exon %s | Start: %s | End: %s | Length: %s' %
                              (exon, str(ex_start), str(ex_end), str(ex_end - ex_start)))
            sequence = exon_dict['sequence']

            line_count = 0

            for char in sequence:
                # Stop each line at a specific length
                # Remainder method prevents count being
                # print amino_acid_counter
                if line_count % 60 == 0:
                    wait_value = 0
                    amino_wait = 0
                    self.line_printer(number_string)
                    self.line_printer(dna_string)
                    if self.amino_spacing: self.line_printer(amino_string)
                    self.line_printer(amino_number_string)
                    if self.amino_spacing: self.line_printer('  ')
                    amino_string = []
                    number_string = []
                    dna_string = []
                    amino_number_string = []
                    self.exon_spacing = False
                    self.amino_spacing = False

                dna_string.append(char)

                if char.isupper(): self.exon_printed = True
                if cds_count == 0:
                    self.amino_printing = True
                    cds_count = 1
                if amino_acid_counter >= len(protein): self.amino_printing = False

                # Calls specific methods for character decision
                # Simplifies local logic
                (next_amino_string, codon_count, amino_acid_counter,
                 codon_numbered) = self.decide_amino_string_character(char, codon_count, amino_acid_counter,
                                                                      codon_numbered, protein)
                amino_string.append(next_amino_string)

                (next_amino_number, amino_wait, codon_numbered,
                 amino_acid_counter) = self.decide_amino_number_string_character(amino_wait, codon_numbered,
                                                                            amino_acid_counter)
                amino_number_string.append(next_amino_number)

                (next_number_string, wait_value, cds_count, amino_acid_counter, post_protein_printer, intron_offset,
                 intron_in_padding, intron_out) = self.decide_number_string_character(char, wait_value, cds_count,
                                                                                      amino_acid_counter,
                                                                                      post_protein_printer,
                                                                                      intron_offset, intron_in_padding,
                                                                                      len(protein), intron_out)
                number_string.append(next_number_string)

                line_count += 1

            # Section for incomplete lines (has not reached line-limit print)
            # Called after exon finishes printing bases
            if len(dna_string) != 0:
                wait_value = 0
                amino_wait = 0
                self.line_printer(number_string)
                self.line_printer(dna_string)
                if not self.amino_spacing: self.line_printer(amino_string)
                self.line_printer(amino_number_string)
                if self.amino_spacing: self.line_printer('  ')

        if self.write_as_LaTex:
            self.print_latex_footer()

    def print_latex_footer(self):

        '''
        A brief function to set the final lines of the document if the output
        is to be in a LaTex parse-able format
        '''
        self.line_printer('\\end{Verbatim}')
        self.line_printer('\\end{document}')

    def line_printer(self, string):

        '''
        :param string: next string to be written to output list
        :return: none

        Generic print method to handle all list output in one location
        '''
        self.output_list.append(''.join(string))

    def decide_amino_number_string_character(self, amino_wait, codon_numbered, amino_acid_counter):
        output = ''
        if amino_wait != 0:
            amino_wait -= 1
        elif amino_wait == 0:
            if amino_acid_counter % 10 == 1:
                if not codon_numbered:
                    output = '|' + str(amino_acid_counter)
                    amino_wait = len(str(amino_acid_counter))
                    codon_numbered = True
                elif codon_numbered:
                    # NOT SURE - condition shouldn't occur
                    output = ' '
            elif amino_acid_counter % 10 != 1:
                output = ' '
        return output, amino_wait, codon_numbered, amino_acid_counter

    def run(self):
        self.print_latex()
        return self.output_list
