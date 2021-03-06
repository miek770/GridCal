# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.
import os
import json
import sys
from warnings import warn

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.IO.json_parser import save_json_file
from GridCal.Engine.IO.cim_parser import CIMExport
from GridCal.Engine.IO.excel_interface import save_excel, load_from_xls, interpret_excel_v3, interprete_excel_v2, \
                                               create_data_frames
from GridCal.Engine.IO.matpower_parser import interpret_data_v1
from GridCal.Engine.IO.dgs_parser import dgs_to_circuit
from GridCal.Engine.IO.matpower_parser import parse_matpower_file
from GridCal.Engine.IO.dpx_parser import load_dpx
from GridCal.Engine.IO.ipa_parser import load_iPA
from GridCal.Engine.IO.json_parser import parse_json
from GridCal.Engine.IO.psse_parser import PSSeParser
from GridCal.Engine.IO.cim_parser import CIMImport
from GridCal.Engine.IO.zip_interface import save_data_frames_to_zip, open_data_frames_from_zip


from PySide2.QtCore import QThread, Signal


class FileOpen:

    def __init__(self, file_name):
        """
        File open handler
        :param file_name: name of the file
        """
        self.file_name = file_name

        self.circuit = MultiCircuit()

        self.logger = list()

    def open(self, text_func=None, progress_func=None):
        """
        Load GridCal compatible file
        :param text_func: pointer to function that prints the names
        :param progress_func: pointer to function that prints the progress 0~100
        :return: logger with information
        """
        logger = list()

        if os.path.exists(self.file_name):
            name, file_extension = os.path.splitext(self.file_name)
            # print(name, file_extension)
            if file_extension.lower() in ['.xls', '.xlsx']:

                data_dictionary = load_from_xls(self.file_name)

                # Pass the table-like data dictionary to objects in this circuit
                if 'version' not in data_dictionary.keys():

                    interpret_data_v1(self.circuit, data_dictionary)
                    # return self.circuit
                elif data_dictionary['version'] == 2.0:
                    interprete_excel_v2(self.circuit, data_dictionary)
                    # return self.circuit
                elif data_dictionary['version'] == 3.0:
                    interpret_excel_v3(self.circuit, data_dictionary)
                    # return self.circuit
                else:
                    warn('The file could not be processed')
                    # return self.circuit

            elif file_extension.lower() == '.gridcal':

                # open file content
                data_dictionary = open_data_frames_from_zip(self.file_name,
                                                            text_func=text_func,
                                                            progress_func=progress_func)
                # interpret file content
                interpret_excel_v3(self.circuit, data_dictionary)

            elif file_extension.lower() == '.dgs':
                circ = dgs_to_circuit(self.file_name)
                self.circuit.buses = circ.buses
                self.circuit.branches = circ.branches
                self.circuit.assign_circuit(circ)

            elif file_extension.lower() == '.m':
                circ = parse_matpower_file(self.file_name)
                self.circuit.buses = circ.buses
                self.circuit.branches = circ.branches
                self.circuit.assign_circuit(circ)

            elif file_extension.lower() == '.dpx':
                circ, logger = load_dpx(self.file_name)
                self.circuit.buses = circ.buses
                self.circuit.branches = circ.branches
                self.circuit.assign_circuit(circ)

            elif file_extension.lower() == '.json':

                # the json file can be the GridCAl one or the iPA one...
                data = json.load(open(self.file_name))

                if type(data) == dict():
                    if 'Red' in data.keys():
                        circ = load_iPA(self.file_name)
                        self.circuit.buses = circ.buses
                        self.circuit.branches = circ.branches
                        self.circuit.assign_circuit(circ)
                    else:
                        logger.append('Unknown json format')

                elif type(data) == list():
                    circ = parse_json(self.file_name)
                    self.circuit.buses = circ.buses
                    self.circuit.branches = circ.branches
                    self.circuit.assign_circuit(circ)
                else:
                    logger.append('Unknown json format')

            elif file_extension.lower() == '.raw':
                parser = PSSeParser(self.file_name)
                circ = parser.circuit
                self.circuit.buses = circ.buses
                self.circuit.branches = circ.branches
                self.circuit.assign_circuit(circ)
                logger = parser.logger

            elif file_extension.lower() == '.xml':
                parser = CIMImport()
                circ = parser.load_cim_file(self.file_name)
                self.circuit.assign_circuit(circ)
                logger = parser.logger

        else:
            warn('The file does not exist.')
            logger.append(self.file_name + ' does not exist.')

        self.logger = logger

        return self.circuit


class FileSave:

    def __init__(self, circuit: MultiCircuit, file_name, text_func=None, progress_func=None):
        """
        File saver
        :param circuit: MultiCircuit
        :param file_name: file name to save to
        :param text_func: Pointer to the text function
        :param progress_func: Pointer to the progress function
        """
        self.circuit = circuit

        self.file_name = file_name

        self.text_func = text_func

        self.progress_func = progress_func

    def save(self):
        """
        Save the file in the corresponding format
        :return: logger with information
        """
        if self.file_name.endswith('.xlsx'):
            logger = self.save_excel()

        elif self.file_name.endswith('.gridcal'):
            logger = self.save_zip()

        elif self.file_name.endswith('.json'):
            logger = self.save_json()

        elif self.file_name.endswith('.xml'):
            logger = self.save_cim()

        else:
            logger = list()
            logger.append('File path extension not understood\n' + self.file_name)

        return logger

    def save_excel(self):
        """
        Save the circuit information in excel format
        :return: logger with information
        """

        logger = save_excel(self.circuit, self.file_name)

        return logger

    def save_zip(self):
        """
        Save the circuit information in zip format
        :return: logger with information
        """

        logger = list()

        dfs = create_data_frames(self.circuit)

        save_data_frames_to_zip(dfs,
                                filename_zip=self.file_name,
                                text_func=self.text_func,
                                progress_func=self.progress_func)

        return logger

    def save_json(self):
        """
        Save the circuit information in json format
        :return:logger with information
        """

        logger = save_json_file(self.file_name, self.circuit)
        return logger

    def save_cim(self):
        """
        Save the circuit information in CIM format
        :return: logger with information
        """

        cim = CIMExport(self.circuit)
        cim.save(file_name=self.file_name)

        return cim.logger


class FileOpenThread(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()

    def __init__(self, file_name):
        """
        Constructor
        :param file_name: file name were to save
        """
        QThread.__init__(self)

        self.file_name = file_name

        self.valid = False

        self.logger = list()

        self.circuit = None

        self.__cancel__ = False

    def run(self):
        """
        run the file open procedure
        """
        self.circuit = MultiCircuit()

        path, fname = os.path.split(self.file_name)

        self.progress_text.emit('Loading ' + fname + '...')

        self.logger = list()

        file_handler = FileOpen(file_name=self.file_name)

        self.circuit = file_handler.open(text_func=self.progress_text.emit,
                                         progress_func=self.progress_signal.emit)

        self.logger += file_handler.logger
        self.valid = True

        # post events
        self.progress_text.emit('Done!')

        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True


class FileSaveThread(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()

    def __init__(self, circuit: MultiCircuit, file_name):
        """
        Constructor
        :param circuit: MultiCircuit instance
        :param file_name: name of the file where to save
        """
        QThread.__init__(self)

        self.circuit = circuit

        self.file_name = file_name

        self.valid = False

        self.logger = list()

        self.error_msg = ''

        self.__cancel__ = False

    def run(self):
        """
        run the file save procedure
        @return:
        """

        try:
            path, fname = os.path.split(self.file_name)

            self.progress_text.emit('Flushing ' + fname + ' into ' + fname + '...')

            self.logger = list()

            file_handler = FileSave(self.circuit,
                                    self.file_name,
                                    text_func=self.progress_text.emit,
                                    progress_func=self.progress_signal.emit)

            self.logger = file_handler.save()

            self.valid = True

            # post events
            self.progress_text.emit('Done!')

        except:
            self.valid = False
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.logger.append(str(exc_traceback) + '\n' + str(exc_value))

        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True