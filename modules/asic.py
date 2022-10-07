# -*- coding: utf-8 -*-
""""""
"""
Created on Fri Jun 25 16:28:27 2021

@author: Nicolas Striebig

Astropix2 Configbits
"""
import yaml
import logging

from bitstring import BitArray
from dataclasses import dataclass

from modules.nexysio import Nexysio
from modules.setup_logger import logger


logger = logging.getLogger(__name__)

class Asic(Nexysio):
    """Configure ASIC"""

    def __init__(self, handle) -> None:

        self._handle = handle

        self._chipversion = None

        self._num_rows = 35
        self._num_cols = 35

        self.asic_config = None

    @property
    def chipversion(self):
        """Get/set chipversion

        :returns: chipversion
        """
        return self._chipversion

    @chipversion.setter
    def chipversion(self, chipversion):
        self._chipversion = chipversion

    @property
    def num_cols(self):
        """Get/set number of columns

        :returns: Number of columns
        """
        return self._num_cols

    @num_cols.setter
    def num_cols(self, cols):
        self._num_cols = cols

    @property
    def num_rows(self):
        """Get/set number of rows

        :returns: Number of rows
        """
        return self._num_rows

    @num_rows.setter
    def num_rows(self, rows):
        self._num_rows = rows

    def enable_inj_row(self, row: int):
        """Enable Row injection switch

        :param row: Row number
        """
        if(row < self.num_rows):
            self.asic_config['recconfig'][f'col{row}'][1] = self.asic_config['recconfig'].get(f'col{row}', 0b001_11111_11111_11111_11111_11111_11111_11110)[1] | 0b000_00000_00000_00000_00000_00000_00000_00001

    def enable_inj_col(self, col: int):
        """Enable col injection switch

        :param col: Col number
        """
        if(col < self.num_cols):
            self.asic_config['recconfig'][f'col{col}'][1] = self.asic_config['recconfig'].get(f'col{col}', 0b001_11111_11111_11111_11111_11111_11111_11110)[1] | 0b010_00000_00000_00000_00000_00000_00000_00000

    def enable_ampout_col(self, col: int):
        """Select Col for analog mux and disable other cols

        :param col: Col number
        """
        for i in range(self.num_cols):
            self.asic_config['recconfig'][f'col{i}'][1] = self.asic_config['recconfig'][f'col{i}'][1] & 0b011_11111_11111_11111_11111_11111_11111_11111

        self.asic_config['recconfig'][f'col{col}'][1] = self.asic_config['recconfig'][f'col{col}'][1] | 0b100_00000_00000_00000_00000_00000_00000_00000

    def enable_pixel(self, col: int, row: int):
        """Enable pixel comparator for specified pixel

        :param col: Col number
        :param row: Row number
        """
        if(row < self.num_rows and col < self.num_cols):
            self.asic_config['recconfig'][f'col{col}'][1] = self.asic_config['recconfig'].get(f'col{col}', 0b001_11111_11111_11111_11111_11111_11111_11110)[1] & ~(2 << row)

    def disable_pixel(self, col: int, row: int):
        """Disable pixel comparator for specified pixel

        :param col: Col number
        :param row: Row number
        """
        if(row < self.num_rows and col < self.num_cols):
            self.asic_config['recconfig'][f'col{col}'][1] = self.asic_config['recconfig'].get(f'col{col}', 0b001_11111_11111_11111_11111_11111_11111_11110)[1] | (2 << row)

    def disable_inj_row(self, row: int):
        """Disable row injection switch

        :param row: Row number
        """
        if(row < self.num_rows):
            self.asic_config['recconfig'][f'col{row}'][1] = self.asic_config['recconfig'].get(f'col{row}', 0b001_11111_11111_11111_11111_11111_11111_11110)[1] & 0b111_11111_11111_11111_11111_11111_11111_11110

    def disable_inj_col(self, col: int):
        """Disable col injection switch

        :param col: Col number
        """
        if(col < self.num_cols):
            self.asic_config['recconfig'][f'col{col}'][1] = self.asic_config['recconfig'].get(f'col{col}', 0b001_11111_11111_11111_11111_11111_11111_11110)[1] & 0b101_11111_11111_11111_11111_11111_11111_11111

    def get_pixel(self, col: int, row: int):
        """Check if Pixel is enabled

        :param col: Col number
        :param row: Row number
        """
        if(row < self.num_rows):
            if( self.asic_config['recconfig'].get(f'col{col}')[1] & (1<<(row+1))):
                return False
            else:
                return True

    def reset_recconfig(self):
        """Reset recconfig by disabling all pixels and disabling all injection switches and mux ouputs
        """
        for key in self.asic_config['recconfig']:
            self.asic_config['recconfig'][key][1] = 0b001_11111_11111_11111_11111_11111_11111_11110

    @staticmethod
    def __int2nbit(value: int, nbits: int) -> BitArray:
        """Convert int to 6bit bitarray

        :param value: Integer value
        :param nbits: Number of bits

        :returns: Bitarray of specified length
        """

        try:
            return BitArray(uint=value, length=nbits)
        except ValueError:
            print(f'Allowed Values 0 - {2**nbits-1}')

    def load_conf_from_yaml(self, chipversion: int, filename: str):
        """Load ASIC config from yaml


        :param filename: Name of yml file in config folder
        """
        self.chipversion = chipversion

        with open(f"config/{filename}.yml", "r") as stream:
            try:
                dict_from_yml = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                logger.error(exc)

        try:
            self.asic_config = dict_from_yml.get(f'astropix{chipversion}')['config']
            logger.info(f"Astropix{chipversion} config found!")
        except:
            logger.error(f"Astropix{chipversion} config not found")

        try:
            self.num_cols = dict_from_yml[f'astropix{chipversion}'].get('geometry')['cols']
            self.num_rows = dict_from_yml[f'astropix{chipversion}'].get('geometry')['rows']
            logger.info(f"Astropix{chipversion} matrix dimensions found!")
        except:
            logger.error(f"Astropix{chipversion} matrix dimensions not found!")

    def write_conf_to_yaml(self, chipversion: int, filename: str):
        """Write ASIC config to yaml

        :param chipversion: Name of yml file in config folder
        :param filename: Name of yml file in config folder
        """
        with open(f"config/{filename}.yml", "w") as stream:
            try:
                yaml.dump({f"astropix{chipversion}": \
                    {
                        "geometry": {"cols": self.num_cols, "rows": self.num_rows},\
                        "config" : self.asic_config}\
                    },
                    stream, default_flow_style=False, sort_keys=False)

            except yaml.YAMLError as exc:
                logger.error(exc)


    def gen_asic_vector(self, msbfirst: bool = False) -> BitArray:
        """Generate asic bitvector from digital, bias and dacconfig

        :param msbfirst: Send vector MSB first
        """

        bitvector = BitArray()

        for key in self.asic_config:
            for values in self.asic_config[key].values():
                bitvector.append(self.__int2nbit(values[1], values[0]))

        if not msbfirst:
            bitvector.reverse()

        return bitvector

    def update_asic(self) -> None:
        """Update ASIC"""

        if self.chipversion == 1:
            dummybits = self.gen_asic_pattern(BitArray(uint=0, length=245), True) # Not needed for v2
            self.write(dummybits)

        # Write config
        asicbits = self.gen_asic_pattern(self.gen_asic_vector(), True)
        self.write(asicbits)

    def readback_asic(self):
        asicbits = self.gen_asic_pattern(self.gen_asic_vector(), True, readback_mode = True)
        print(asicbits)
        self.write(asicbits)
