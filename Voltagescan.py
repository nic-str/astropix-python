"""
Code to run power supply bias voltage scanning with a source. This will not be near as robust as the beam_test.py
but since it is just for my use (for now) I think it will do. 
"""

from astropix import astropix2
import pandas as pd
import numpy as np
import logging
import binascii
import time 
import os
#import [CONTROL PKG] as RC
from modules.setup_logger import logger


datadir = "biasscan_source"
psudir = "ps"
digitdir = "digital"

vmin = -5
vmax = -135
vstep = -10

testlen = 60

psu_ip = ''

maxlen = 4 * 60 * 60


pspath = datadir + '/' + psudir
csvpath = datadir + '/' + digitdir

basecrrnt = f"/bias_scan_{vmin}_{vmax}_{vstep}_Source_Ba-133_CURRENTS" + time.strftime("%Y%m%d-%H%M%S")
basedigit = f"/bias_scan_{vmin}_{vmax}_{vstep}_Source_Ba-133_DIGITAL" + time.strftime("%Y%m%d-%H%M%S")
basebits = f"/bias_scan_{vmin}_{vmax}_{vstep}_Source_Ba-133_BITSTREAMS" + time.strftime("%Y%m%d-%H%M%S")


if os.path.exists(pspath) == False:
    os.mkdir(pspath)
if os.path.exists(csvpath) == False:
    os.mkdir(csvpath)

# This sets the logger name.
logdir = "./runlogs/"
if os.path.exists(logdir) == False:
    os.mkdir(logdir)
logname = "./runlogs/AstropixRunlog_" + time.strftime("%Y%m%d-%H%M%S") + ".log"

decode_fail_frame = pd.DataFrame({
                'readout': np.nan,
                'Chip ID': np.nan,
                'payload': np.nan,
                'location': np.nan,
                'isCol': np.nan,
                'timestamp': np.nan,
                'tot_msb': np.nan,
                'tot_lsb': np.nan,
                'tot_total': np.nan,
                'tot_us': np.nan,
                'hittime': np.nan
                }, index=[0]
)




def getData(astro:astropix2, PS, runtime, bias, basecrrnt, basedigit, basebits):

    maxtime = time.time() + runtime
    crrntpth = basecrrnt + f"_{bias}V_bias.csv"
    digitpth = basedigit + f"_{bias}V_bias.csv"
    bitspth = basebits + f"_{bias}V_bias.log"

    csvframe =pd.DataFrame(columns = [
        'readout',
        'Chip ID',
        'payload',
        'location',
        'isCol',
        'timestamp',
        'tot_msb',
        'tot_lsb',
        'tot_total',
        'tot_us',
        'hittime'])
    
    
    bitfile = open(bitspth, 'w')
    bitfile.write(astro.get_log_header())

    returnval = 0

    errors = 0
    maxerrors = 10
    try:
        while (time.time() <= maxtime) and (errors <= maxerrors):

            if astro.hits_present(): # Checks if hits are present
                time.sleep(.1) # this is probably not needed, will ask Nicolas

                readout = astro.get_readout() # Gets the bytearray from the chip
                # Writes the hex version to hits
                bitfile.write(f"{i}\t{str(binascii.hexlify(readout))}\n")
                print(binascii.hexlify(readout))

                # Added fault tolerance for decoding, the limits of which are set through arguments
                try:
                    hits = astro.decode_readout(readout, i, printer = True)

                except IndexError:
                    errors += 1
                    logger.warning(f"Decoding failed. Failure {errors} of {maxerrors} on readout {i}")
                    # We write out the failed decode dataframe
                    hits = decode_fail_frame
                    hits.readout = i
                    hits.hittime = time.time()

                        # This loggs the end of it all 
                    if errors > maxerrors:
                        logger.warning(f"Decoding failed {errors} times on an index error. Terminating Progam...")
                        returnval = 10
                finally:
                        i += 1
                        errors += 1
                        csvframe = pd.concat([csvframe, hits])
    except KeyboardInterrupt:
        logger.info("Recieved Interrupt. Terminating program...")
    finally:
        csvframe.index.name = "dec_order"
        csvframe.to_csv(csvpath)
        # NEEDS TO BE FINISHED
        data, nrows = PS.StopColection()
        df = PS.to_csv(data, nrows)
        df.to_csv(crrntpth)

    return returnval


def main():
    astro = astropix2()
    astro.asic_init()
    astro.init_voltages()
    astro.init_injection()
    astro.enable_spi() 
    logger.info("Chip configured")
    astro.dump_fpga()
    try:
        for bias in range(vmin, vmax, vstep):
            cont = getData(astro, PS, testlen, bias, basecrrnt, basedigit, basebits)
            if cont == 10:
                raise RuntimeError("Maximum errors exceded!")
    except KeyboardInterrupt:
        logger.info("Keyboard interup. Terminating...")

    except Exception as e:
        logger.exception(f"e")



if __name__ == "__main__":
    formatter = logging.Formatter('%(asctime)s:%(msecs)d.%(name)s.%(levelname)s:%(message)s')
    fh = logging.FileHandler(logname)
    fh.setFormatter(formatter)
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)

    logging.getLogger().addHandler(sh) 
    logging.getLogger().addHandler(fh)
    logging.getLogger().setLevel(logging.DEBUG)

    logger = logging.getLogger(__name__)

    main()

