# -*- coding: utf-8 -*-
""""""
"""
Created on Tue Dec 28 19:03:40 2021

@author: Nicolas Striebig
"""

import pandas as pd
import re
import math
import binascii
from bitstring import BitArray

import logging
from modules.setup_logger import logger


logger = logging.getLogger(__name__)

class Decode:
    def __init__(self, sampleclock_period_ns = 5):
        self.sampleclock_period_ns = sampleclock_period_ns
        self.bytesperhit = 5

    def reverse_bitorder(self, data: bytearray) -> bytearray:
        for index, item in enumerate(data):

            item_rev = BitArray(uint=item, length=8)
            item_rev.reverse()

            data[index] = item_rev.uint

        return data

    def hits_from_readoutstream(self, readout: bytearray, reverse_bitorder: bool = True) -> list:
        """
        Find hits in readoutstream

        :param readout: Readout stream
        :param reverse_bitorder: Reverse Bitorder per byte

        :returns: Position of hits in the datastream
        """

        length = len(readout)
        hitlist = []
        i=0

        #require one idle byte
        #idle_byte = 0xbc if reverse_bitorder else 0x3d
        #require two idle bytes
        idle_byte = 0xbcbc if reverse_bitorder else 0x3d3d


        while i < length:
            if readout[i] == idle_byte or readout[i] == 0xff:
                i += 1
            else:
                if reverse_bitorder:
                    hitlist.append(self.reverse_bitorder(readout[i:i + self.bytesperhit]))
                else:
                    hitlist.append(readout[i : i + self.bytesperhit])

                i += self.bytesperhit

        return hitlist

    def decode_astropix2_hits(self, list_hits: list) -> pd.DataFrame:
        """
        Decode 5byte Frames from AstroPix 2

        Byte 0: Header      Bits:   7-3: ID
                                    2-0: Payload
        Byte 1: Location            7: Col
                                    6: reserved
                                    5-0: Row/Col
        Byte 2: Timestamp
        Byte 3: ToT MSB             7-4: 4'b0
                                    3-0: ToT MSB
        Byte 4: ToT LSB

        :param list_hists: List with all hits

        :returns: Dataframe with decoded hits
        """

        hit_pd = []

        for hit in list_hits:
            if len(hit) == self.bytesperhit:
                id          = int(hit[0]) >> 3
                payload     = int(hit[0]) & 0b111
                location    = int(hit[1])  & 0b111111
                col         = 1 if (int(hit[1]) >> 7 ) & 1 else 0
                timestamp   = int(hit[2])
                tot_msb     = int(hit[3]) & 0b1111
                tot_lsb     = int(hit[4])
                tot_total   = (tot_msb << 8) + tot_lsb

                #hit_pd = hit_pd.append({'id': id,'payload': payload,'location': location, 'col': col, 'timestamp': timestamp, 'tot_total': tot_total}, ignore_index=True)
                hit_pd.append([id, payload, location, col, timestamp, tot_total])
                logger.info(
                    "Header: ChipId: %d\tPayload: %d\n"
                    "Location: %d\tRow/Col: %d\n"
                    "Timestamp: %d\n"
                    "ToT: MSB: %d\tLSB: %d Total: %d (%d us)",
                    id, payload, location, col, timestamp, tot_msb, tot_lsb, tot_total, (tot_total * self.sampleclock_period_ns)/1000.0
                )

        return pd.DataFrame(hit_pd, columns=['id','payload','location', 'col', 'timestamp', 'tot_total'])

    ###################################################################################################
    ################################### Old decoding, to be removed ###################################
    ###################################################################################################

    def hits_from_readoutstream_old(self, readout: bytearray, reverse_bitorder: bool = True) -> list:
        """
        Extract Hits from Readout stream

        :param readout: Readout streeam
        :param reverse_bitorder: Reverse Bitorder per byte

        :returns: List of hits
        """

        if type(readout) == list: readout=bytearray(readout)

        #Reverse Bitorder per byte
        if reverse_bitorder:
            readout = self.reverse_bitorder(readout)

        matches = self.find_idle_bytes_pos(readout)

        # print(f"Matches: {matches}")

        count = 0

        list_hits = []

        if len(matches) > 1:  # if no hits, there is one tuple (0:end)
            for index, match in enumerate(matches[:-1]):  #e xclude last item
                logger.info(f"Hit: {binascii.hexlify(readout[match[1]:(match[1] + 5)])}")
                match2 = 5 + match[1]

                list_hits.append(readout[match[1]:(match[1] + 5)])

                count += 1

                if index < len(matches) - 1:
                    while matches[index + 1][0] > match2:  # and matches[index+1][1] < len(readout):
                        logger.debug(f"Match: {match2} next: {matches[index + 1]}")
                        logger.info(f"Hit: {binascii.hexlify(readout[match2:(match2 + 5)])}")

                        list_hits.append(readout[match2:(match2 + 5)])
                        match2 += 5
                        count += 1

        logger.info(f"Number of Hits {count}")
        logger.debug(f" Hitlist: {list_hits}")

        return list_hits

    def find_idle_bytes_pos(self, readout: bytearray,
            start_seq: bytearray = b'(\x3d{1,})[\0-\x0F]', #b'(\x3d*)',
            idle_seq: bytearray = b'(\x3d{1,})[\0-\x0F]',
            end_seq: bytearray = b'(\x3d{1,})') -> list:
        """
            Find idle Bytes

        :param readout: Readout stream
        :param start_seq: Start sequence regex
        :param idle_seq: Idle sequence regex
        :param end_seq: end sequence regex

        :returns: Tuples with idle byte strings start and stop pos
        """
        matches = []

        # Look for start seq
        start = re.search(start_seq, readout)
        if start is not None:
            matches.append((start.start(), start.end() - 1))

        # Find idle seqs and append to list
        for index, match in enumerate(re.finditer(idle_seq, readout)):
            match_start = match.start()
            match_end = match.end() - 1

            if len(matches) > 0:
                match_start = matches[index][1] + math.ceil((match_start - matches[index][1]) / 5) * 5

            matches.append((match_start, match_end))

        # Look for stop seq
        stop = re.search(end_seq, readout[(matches[-1][1]):])
        if stop is not None:
            matches.append((matches[-1][1]+stop.start(), matches[-1][1]+stop.end()))

        # remove probably redundant first match
        if len(matches) > 1:
            if matches[0][1] == matches[1][1]:
                del matches[1]

        logger.info(f"Matches: {matches}")

        return matches

    def decode_astropix2_hits_old(self, list_hits: list) -> pd.DataFrame:
        """
        Decode 5byte Frames from AstroPix 2

        Byte 0: Header      Bits:   7-3: ID
                                    2-0: Payload
        Byte 1: Location            7: Col
                                    6: reserved
                                    5-0: Row/Col
        Byte 2: Timestamp
        Byte 3: ToT MSB             7-4: 4'b0
                                    3-0: ToT MSB
        Byte 4: ToT LSB

        :param list_hists: List with all hits

        :returns: Dataframe with decoded hits
        """

        hit_pd = pd.DataFrame(columns=['id','payload','location', 'col', 'timestamp', 'tot_total'])

        for hit in list_hits:
            if len(hit) == self.bytesperhit:
                id          = int(hit[0]) >> 3
                payload     = int(hit[0]) & 0b111
                location    = int(hit[1])  & 0b111111
                col         = 1 if (int(hit[1]) >> 7 ) & 1 else 0
                timestamp   = int(hit[2])
                tot_msb     = int(hit[3]) & 0b1111
                tot_lsb     = int(hit[4])
                tot_total   = (tot_msb << 8) + tot_lsb

                hit_pd = hit_pd.append({'id': id,'payload': payload,'location': location, 'col': col, 'timestamp': timestamp, 'tot_total': tot_total}, ignore_index=True)

                logger.info(
                    "Header: ChipId: %d\tPayload: %d\n"
                    "Location: %d\tRow/Col: %d\n"
                    "Timestamp: %d\n"
                    "ToT: MSB: %d\tLSB: %d Total: %d (%d us)",
                    id, payload, location, col, timestamp, tot_msb, tot_lsb, tot_total, (tot_total * self.sampleclock_period_ns)/1000.0
                )

        return hit_pd