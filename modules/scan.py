import time

from tqdm.auto import tqdm

import numpy as np
import logging
import binascii

import pandas as pd

from modules.asic import Asic
from modules.nexysio import Nexysio
from modules.decode import Decode
from modules.setup_logger import logger

logger = logging.getLogger(__name__)

class Scan(Asic, Nexysio):

    def __init__(self, handle=0) -> None:
        self._handle = handle

    @staticmethod
    def threshold_scan_legacy(asic, vboard, injboard, nexys, file, **kwargs):
            ### TODO: Needs to be updated

            decode = Decode()

            noise_run = kwargs.get('noise_run', True)
            vth_start = kwargs.get('vth_start', 1.0)
            stepsize = kwargs.get('stepsize', 0.01)
            steps = kwargs.get('steps', 10)
            counts = kwargs.get('counts', 5)
            vth_stop = kwargs.get('vth_stop', 1.2)
            up = kwargs.get('up', True)
            th_up = kwargs.get('th_up', 1)
            th_down = kwargs.get('th_down', 10)
            #vboard_Vth = kwargs.get('vth', 1.1)
            vboard_BL = kwargs.get('vboard_BL', 1)
            vboard_VCasc2 = kwargs.get('vboard_VCasc2', 1.1)
            vboard_Vminus = kwargs.get('vboard_Vminus', 0.8)

            for col in tqdm(range(asic.num_cols), position=0, leave=False, desc='Column'):

                asic.reset_recconfig()
                asic.enable_ampout_col(col) # enable ampout for current col
                if not kwargs.get('noise_run',0):
                    asic.enable_inj_col(col)

                for row in tqdm(range(asic.num_rows), position=1, leave=False, desc='Row   '):

                    if not noise_run:
                        asic.enable_inj_row(row)
                    asic.enable_pixel(col,row)
                    asic.update_asic()

                    average_per_step = np.zeros(steps)

                    file.write(f"{col},{row}")

                    for step in tqdm(range(steps), position=2, leave=False, desc='Step  '):
                        if up:
                            vboard.dacvalues = (8, [0, 0, vboard_VCasc2, vboard_BL, 0, 0, vboard_Vminus, vth_start+stepsize*step]) # 3 = Vcasc2, 4=BL, 7=Vminuspix, 8=Thpix
                        else:
                            vboard.dacvalues = (8, [0, 0, vboard_VCasc2, vboard_BL, 0, 0, vboard_Vminus, vth_stop-stepsize*step]) # 3 = Vcasc2, 4=BL, 7=Vminuspix, 8=Thpix
                        vboard.update_vb()
                        nexys.spi_reset()
                        nexys.chip_reset()
                        time.sleep(0.1)

                        hit_per_iter = np.zeros(counts)

                        for count in tqdm(range(counts), position=3, leave=False, desc='Count '):
                            if up:
                                tqdm.write(f"Pixel Col: {col} Row: {row} Vth: {vth_start+stepsize*step} Run: {count}")
                                logger.info(f"Pixel Col: {col} Row: {row} Vth: {vth_start+stepsize*step} Run: {count}")
                            else:
                                tqdm.write(f"##### Pixel Col: {col} Row: {row} Vth: {vth_stop-stepsize*step} Run: {count}")
                                logger.info(f"Pixel Col: {col} Row: {row} Vth: {vth_stop-stepsize*step} Run: {count}")

                            if not (noise_run):
                                injboard.start()
                                time.sleep(.5)
                                injboard.stop()

                            nexys.write_spi_bytes(100)

                            readout = nexys.read_spi_fifo()
                            time.sleep(.2)
                            nexys.spi_reset()

                            logger.debug(binascii.hexlify(readout))

                            try:
                                list_hits = decode.hits_from_readoutstream(readout)
                                decode.decode_astropix2_hits(list_hits)
                                tqdm.write(f'{len(list_hits)} Hits found!')
                                logger.info(f'{len(list_hits)} Hits found!')
                                hit_per_iter[count] = len(list_hits)
                            except IndexError:
                                logger.info("No hits found")
                                hit_per_iter[count] = 0
                                pass


                        mean_hits_per_iter = np.mean(hit_per_iter)


                        logger.debug(f"average: {mean_hits_per_iter}")
                        average_per_step[step] = mean_hits_per_iter
                        file.write(f",{mean_hits_per_iter}")


                        if mean_hits_per_iter <= th_up and up:
                            logger.debug("Break: avg. hits 0")
                            break
                        elif mean_hits_per_iter >= th_down and not up:
                            logger.debug("Break: avg. hits > %f", th_down)
                            break

                    asic.disable_pixel(col,row)
                    logger.info("avg. Hits per step %f", average_per_step)
                    file.write("\n")

                    asic.disable_pixel(col,row)

    @staticmethod
    def inj_scan(asic, vboard, injboard, nexys, file, **kwargs):

        decode = Decode()

        noise_run = False
        vinj_start = kwargs.get('vinj_start', 0.1)
        vinj_stop = kwargs.get('vinj_stop', 1.0)
        stepsize = kwargs.get('stepsize', 0.01)
        steps = kwargs.get('steps', 10)
        counts = kwargs.get('counts', 5)
        up = kwargs.get('up', True)
        th_up = kwargs.get('th_up', 1)
        th_down = kwargs.get('th_down', 10)
        vboard_Vth = kwargs.get('vth', 1.1)
        vboard_BL = kwargs.get('vboard_BL', 1)
        vboard_VCasc2 = kwargs.get('vboard_VCasc2', 1.1)
        vboard_Vminus = kwargs.get('vboard_Vminus', 1)
        set_col = kwargs.get('col')
        set_row = kwargs.get('row')

        vboard.dacvalues = (8, [0, 0, vboard_VCasc2, vboard_BL, 0, 0, vboard_Vminus, vboard_Vth]) # 3 = Vcasc2, 4=BL, 7=Vminuspix, 8=Thpix
        vboard.update_vb()

        df = pd.DataFrame(columns = ['scan_col', 'scan_row', 'run', 'step', 'id', 'payload', 'location', 'col', 'timestamp', 'tot_total'])

        for col in tqdm(range(asic.num_cols), position=0, leave=False, desc='Column'):

            if 'col' in kwargs and set_col != col:
                continue

            asic.reset_recconfig()
            asic.enable_ampout_col(col) # enable ampout for current col
            if not kwargs.get('noise_run',0):
                asic.enable_inj_col(col)


            for row in tqdm(range(asic.num_rows), position=1, leave=False, desc='Row   '):

                if 'row' in kwargs and set_row != row:
                    continue

                if not noise_run:
                    asic.enable_inj_row(row)
                asic.enable_pixel(col,row)
                asic.update_asic()

                average_per_step = np.zeros(steps)

                for step in tqdm(range(steps), position=2, leave=False, desc='Step  '):

                    if up:
                        injboard.dacvalues = (2, [vinj_start + stepsize * step, 0])
                    else:
                        injboard.dacvalues = (2, [vinj_stop - stepsize * step, 0])

                    nexys.spi_reset()
                    nexys.chip_reset()
                    time.sleep(0.1)

                    hit_per_iter = np.zeros(counts)

                    for count in tqdm(range(counts), position=3, leave=False, desc='Count '):
                        if up:
                            tqdm.write(f"Pixel Col: {col} Row: {row} Vinj: {vinj_start+stepsize*step} Run: {count}")
                            logger.info("Pixel Col: %d Row: %d Vth: %f Run: %d", col, row, vinj_start+stepsize*step, count)
                        else:
                            tqdm.write(f"Pixel Col: {col} Row: {row} Vinj: {vinj_stop-stepsize*step} Run: {count}")
                            logger.info("Pixel Col: %d Row: %d Vth: %f Run: %d", col, row, vinj_stop-stepsize*step, count)

                        if not (noise_run):
                            injboard.start()
                            time.sleep(.5)
                            injboard.stop()

                        nexys.write_spi_bytes(100)

                        readout = nexys.read_spi_fifo()
                        time.sleep(.2)
                        nexys.spi_reset()

                        logger.debug(binascii.hexlify(readout))
                        print(binascii.hexlify(readout))
                        try:
                            list_hits = decode.hits_from_readoutstream(readout)
                            decoded = decode.decode_astropix2_hits(list_hits)
                            decoded = decoded.assign(scan_row=row,scan_col=col,run=count,step=step)

                            df = pd.concat([df,decoded], axis=0, ignore_index=True)[df.columns]

                            tqdm.write('\x1b[0;31;40m{} Hits found!\x1b[0m'.format((len(list_hits))))
                            logger.info("%d Hits found!", len(list_hits))

                            hit_per_iter[count] = len(list_hits)

                        except IndexError:
                            logger.info("No hits found")
                            hit_per_iter[count] = 0

                    mean_hits_per_iter = np.mean(hit_per_iter)


                    logger.debug("average: %f", mean_hits_per_iter)
                    average_per_step[step] = mean_hits_per_iter

                    if mean_hits_per_iter <= th_up and up:
                        logger.debug("Break: avg. hits 0")
                        break
                    elif mean_hits_per_iter >= th_down and not up:
                        logger.debug("Break: avg. hits > %f", th_down)
                        break

                asic.disable_pixel(col,row)
                logger.info("avg. Hits per step %f", average_per_step)

                asic.disable_pixel(col,row)

        df.index.name='index'
        df.to_csv(file, mode='a')