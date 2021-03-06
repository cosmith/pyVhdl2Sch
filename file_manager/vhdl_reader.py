#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
from vhdl_objects.entity import Entity
from vhdl_objects.wire import Wire
from vhdl_objects.library import Library
from tools.options import Options


class Vhdl_reader:

    """
    Vhdl_reader take the .vhd file and return a full entity
    """

    def __init__(self, filename, options):
        self.state = "start_parsing"
        self.lib_part = ""
        self.entity_part = ""

        self.long_file_name = filename
        self.extract_file_name(self.long_file_name)

        self.file = None
        self.entity = None

        self.open_file()
        self.entity = Entity()
        self.parse_vhdl_file()
        self.parse_entity_part()

        if options.verbose == True:
            self.verbose()
        self.close_file()

    def extract_file_name(self, long_file_name):
        self.filename = long_file_name.split("/")[-1]

    def parse_vhdl_file(self):
        vhdl_part = ""
        for raw_line in self.file:
            # remove comemnts and add spaces around some symbols
            raw_line = self.clean_line(raw_line)
            # put all the file on one line
            vhdl_part = vhdl_part + raw_line

        # split the line at each ;
        for raw_line in vhdl_part.split(";"):
            # split the line at each space
            real_words = raw_line.split()
            # the same but  with lowercase
            clean_words = raw_line.lower().split()

            # remove blank line (just in case)
            # need to find a case
            if len(clean_words) == 0:
                continue

            # now the file looks better we can parse it much easier
            # look at it if you want
            # print raw_line
            if self.state == "start_parsing":
                if "entity" in clean_words:
                    if "is" in clean_words:
                        # ok we just found the start of the entity so locate
                        # entity name
                        locate_entity = clean_words.index("entity")
                        self.entity.set_name(real_words[locate_entity + 1])
                        # and look for port definitions
                        self.state = "parse_entity"

                        # if port definition is just after entity (eg no
                        # Generic)

                        if "port" in clean_words:
                            locate_port = clean_words.index("port")
                            for i in range(locate_port, len(clean_words)):
                                self.entity_part += real_words[i] + " "
                            self.entity_part += "\n"
                else:
                    self.lib_part += raw_line + "\n"
            else:
                if self.state == "parse_entity":
                    if "end" in clean_words:
                        locate_end = clean_words.index("end")
                        if real_words[locate_end + 1] == self.entity.name:
                            self.state = "after_entity"
                    else:
                        self.entity_part += raw_line + "\n"

    def parse_entity_part(self):
        state = "start_parsing"
        for raw_line in self.entity_part.split("\n"):
            raw_line = self.clean_line(raw_line)
            clean_words = raw_line.lower().split()
            # Generic not used so we neglect it
            if state == "start_parsing":
                if "port" in clean_words:
                    state = "parse_port"
                    raw_line = self.remove_port_from_text(raw_line)

            if state == "parse_port":
                clean_words = self.clean_line(raw_line).split()
                if len(clean_words) == 0:
                    continue
                self.extract_wire(raw_line)

        pass

    def remove_port_from_text(self, text):
        words_lower = text.split()
        index = words_lower.index("(")
        words = words_lower[index + 1:]
        return " ".join(words)

    def extract_wire(self, vhdl_wire_line):
        """
        Extract a wire details from a line of VHDL code
        """

        wire_property = self.wire_is_a_clock(vhdl_wire_line)

        vhdl_wire_words = vhdl_wire_line.split()

        wire_type = vhdl_wire_words[3].lower()

        if wire_type == "integer" or\
                wire_type == "natural" or\
                wire_type == "positive":

            nb_wires = 32

        if wire_type == "std_logic":
            nb_wires = 1

        if wire_type == "std_logic_vector" or\
                wire_type == "unsigned" or\
                wire_type == "signed":

            bus_direction = vhdl_wire_words[6].lower()
            bus_description = vhdl_wire_words[5:8]
            if bus_direction == "downto":
                upper_val = bus_description[0]
                lower_val = bus_description[2]
                try:  # if upper_val and lower_val are integers
                    nb_wires = int(upper_val) - int(lower_val) + 1
                except:
                    nb_wires = self.compute_wire_number(
                        upper_val, lower_val)

            else:
                upper_val = bus_description[2]
                lower_val = bus_description[0]
                try:  # if upper_val and lower_val are integers
                    nb_wires = int(upper_val) - int(lower_val) + 1
                except:
                    nb_wires = self.compute_wire_number(
                        upper_val, lower_val)

        if vhdl_wire_words[2] == "in":
            self.entity.add_input(Wire(vhdl_wire_words[0], nb_wires, wire_property))

        if vhdl_wire_words[2] == "out" or vhdl_wire_words[2] == "buffer":
            self.entity.add_output(
                Wire(vhdl_wire_words[0], nb_wires, wire_property))

        if vhdl_wire_words[2] == "inout":
            self.entity.add_inout(Wire(vhdl_wire_words[0], nb_wires, wire_property))

    def wire_is_a_clock(self, vhdl_line):
        """
        Check if clk is present in the line.
        Should be improved with a joint Entity/Structure analisys
        """
        if "clk" in vhdl_line.lower():
            wire_property = "clk"
        else:
            wire_property = "classic"
        return wire_property

    def compute_wire_number(self, up, low):
        low = low.replace(" ", "")
        try:
            upper_val = int(up)
            return self.wire_number_upper_is_int(upper_val, low)
        except:
            left_up = up.split("-")[0]
            right_up = up.split("-")[1]
            lower_val = int(low)
            return self.wire_number_upper_is_not_int(left_up, right_up, lower_val)

    def wire_number_upper_is_not_int(self, left_up, right_up, lower_val):
        if -int(right_up) - lower_val + 1 == 0:
            return left_up
        else:
            return left_up + "-" + "%s" % -(-int(right_up) - lower_val + 1)

    def wire_number_upper_is_int(self, upper_val, low):
        try:
            lower_val = int(low)
            return int(upper_val) - int(lower_val) + 1
        except:
            left_low = low.split("-")[0]
            right_low = low.split("-")[1]
            return - int(right_low) + 1 + "-" + upper_val

    def clean_line(self, text):
        clean_line = self.remove_comment(text)
        clean_line = clean_line.replace(':', ' : ')
        clean_line = clean_line.replace('(', ' ( ')
        clean_line = clean_line.replace(')', ' ) ')
        clean_line = clean_line.replace(' -', '-')
        clean_line = clean_line.replace('- ', '-')
        clean_line = clean_line.replace(' ;', ';')
        clean_line = clean_line.replace('\n', '')
        return clean_line

    def remove_comment(self, text):
        words = text.split()
        clean_line = ""
        for i in range(0, len(words)):
            if "--" in words[i]:
                break
            clean_line += words[i] + " "
        return clean_line

    def verbose(self):
        print "input file: %s" % self.filename
        print "entity name: %s" % self.entity.name
        print "%d inputs" % len(self.entity.inputs)
        for i in range(0, len(self.entity.inputs)):
            self.entity.inputs[i].verbose()

        print "%d outputs" % len(self.entity.outputs)
        for i in range(0, len(self.entity.outputs)):
            self.entity.outputs[i].verbose()

        print "%d inouts" % len(self.entity.inouts)
        for i in range(0, len(self.entity.inouts)):
            self.entity.inouts[i].verbose()

        pass

    def open_file(self):
        self.file = open(self.long_file_name, "r")
        pass

    def close_file(self):
        self.file.close()
        pass
