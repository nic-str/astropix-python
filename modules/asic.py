# -*- coding: utf-8 -*-
""""""
"""
Created on Fri Jun 25 16:28:27 2021

@author: Nicolas Striebig

Astropix2 Configbits
"""
from bitstring import BitArray
from dataclasses import dataclass

from modules.nexysio import Nexysio

@dataclass
class Astropix2Config:
    # TODO Improvement: Move Configbits to dedicated dataclass
    pass


class Asic(Nexysio):
    """Configure ASIC"""

    def __init__(self, handle) -> None:

        self._handle = handle

        self._num_rows = 35
        self._num_cols = 35

        self.digitalconfig = {'interrupt_pushpull': 1}

        i = 1
        while i < 19:
            self.digitalconfig[f'En_Inj{i}'] = 0
            i += 1

        self.digitalconfig['ResetB'] = 0

        i = 0
        while i < 8:
            self.digitalconfig[f'Extrabit{i}'] = 1
            i += 1
        while i < 15:
            self.digitalconfig[f'Extrabit{i}'] = 0
            i += 1

        self.biasconfig = {
            'DisHiDR': 0,
            'q01': 0,
            'qon0': 0,
            'qon1': 1,
            'qon2': 0,
            'qon3': 1,
        }

        self.dacs = {
            'blres': 0,
            'nu1': 0,
            'vn1': 20,
            'vnfb': 1,
            'vnfoll': 10,
            'nu5': 0,
            'nu6': 0,
            'nu7': 0,
            'nu8': 0,
            'vn2': 0,
            'vnfoll2': 1,
            'vnbias': 0,
            'vpload': 5,
            'nu13': 0,
            'vncomp': 2,
            'vpfoll': 60,
            'nu16': 0,
            'vprec': 60,
            'vnrec': 30
        }

        # self.dacs = {
        #     'blres': 10,
        #     'nu1': 0,
        #     'vn1': 10,
        #     'vnfb': 10,
        #     'vnfoll': 2,
        #     'nu5': 0,
        #     'nu6': 0,
        #     'nu7': 0,
        #     'nu8': 0,
        #     'vn2': 0,
        #     'vnfoll2': 10,
        #     'vnbias': 10,
        #     'vpload': 2,
        #     'nu13': 0,
        #     'vncomp': 20,
        #     'vpfoll': 20,
        #     'nu16': 0,
        #     'vprec': 30,
        #     'vnrec': 30
        # }

        self.recconfig = {'ColConfig0': 0b001_11111_11111_11111_11111_11111_11111_11110}

        i = 1
        while i < self._num_cols:
            self.recconfig[f'ColConfig{i}'] = 0b001_11111_11111_11111_11111_11111_11111_11110
            i += 1

    def get_num_cols(self):
        return self._num_cols

    def get_num_rows(self):
        return self._num_rows

    def enable_inj_row(self, col: int):
        self.recconfig[f'ColConfig{col}'] = self.recconfig.get(f'ColConfig{col}', 0b001_11111_11111_11111_11111_11111_11111_11110) | 0b000_00000_00000_00000_00000_00000_00000_00001

    def enable_inj_col(self, col: int):
        self.recconfig[f'ColConfig{col}'] = self.recconfig.get(f'ColConfig{col}', 0b001_11111_11111_11111_11111_11111_11111_11110) | 0b010_00000_00000_00000_00000_00000_00000_00000

    def enable_ampout_col(self, col: int):
        self.recconfig[f'ColConfig{col}'] = self.recconfig.get(f'ColConfig{col}', 0b001_11111_11111_11111_11111_11111_11111_11110) | 0b100_00000_00000_00000_00000_00000_00000_00000

        for i in range(self.get_num_cols()):
            if not i == col:
                self.recconfig[f'ColConfig{i}'] = self.recconfig.get(f'ColConfig{col}') & 0b011_11111_11111_11111_11111_11111_11111_11111

    def enable_pixel(self, col: int, row: int):
        if(row < self._num_rows):
            self.recconfig[f'ColConfig{col}'] = self.recconfig.get(f'ColConfig{col}', 0b001_11111_11111_11111_11111_11111_11111_11110) & ~(2 << row)

    def disable_pixel(self, col: int, row: int):
        if(row < self._num_rows):
            self.recconfig[f'ColConfig{col}'] = self.recconfig.get(f'ColConfig{col}', 0b001_11111_11111_11111_11111_11111_11111_11110) | (2 << row)

    def disable_row(self, col: int, row: int):
        if(row < self._num_rows):
            self.recconfig[f'ColConfig{col}'] = self.recconfig.get(f'ColConfig{col}', 0b001_11111_11111_11111_11111_11111_11111_11110) & 0b111_11111_11111_11111_11111_11111_11111_11110

    def disable_col(self, col: int, row: int):
        if(row < self._num_rows):
            self.recconfig[f'ColConfig{col}'] = self.recconfig.get(f'ColConfig{col}', 0b001_11111_11111_11111_11111_11111_11111_11110) & 0b101_11111_11111_11111_11111_11111_11111_11111

    def get_pixel(self, col: int, row: int):
        if(row < self._num_rows):
            if( self.recconfig.get(f'ColConfig{col}') & (1<<(row+1))):
                return False
            else:
                return True

    def reset_recconfig(self):
        i = 0
        while i < self._num_cols:
            self.recconfig[f'ColConfig{i}'] = 0b001_11111_11111_11111_11111_11111_11111_11110
            i += 1

    @staticmethod
    def __int2nbit(value: int, nbits: int) -> BitArray:
        """Convert int to 6bit bitarray

        :param value: DAC value 0-63
        """

        try:
            return BitArray(uint=value, length=nbits)
        except ValueError:
            print(f'Allowed Values 0 - {2**nbits-1}')

    def gen_asic_vector(self, msbfirst: bool = False) -> BitArray:
        """Generate asic bitvector from digital, bias and dacconfig

        :param msbfirst: Send vector MSB first
        """

        bitvector = BitArray()

        for value in self.digitalconfig.values():
            bitvector.append(self.__int2nbit(value, 1))

        for value in self.biasconfig.values():
            bitvector.append(self.__int2nbit(value, 1))

        for value in self.dacs.values():
            bitvector.append(self.__int2nbit(value, 6))

        for value in self.recconfig.values():
            bitvector.append(self.__int2nbit(value, 38))

        if not msbfirst:
            bitvector.reverse()

        # print(f'Bitvector: {bitvector} \n')

        return bitvector

    def update_asic(self) -> None:
        """Update ASIC"""

        # Not needed for v2
        # dummybits = self.gen_asic_pattern(BitArray(uint=0, length=245), True)

        # Write config
        asicbits = self.gen_asic_pattern(self.gen_asic_vector(), True)
        self.write(asicbits)

    def readback_asic(self):
        asicbits = self.gen_asic_pattern(self.gen_asic_vector(), True, readback_mode = True)
        print(asicbits)
        self.write(asicbits)
