"""
Code to run power supply bias voltage scanning with a source. This will not be near as robust as the beam_test.py
but since it is just for my use (for now) I think it will do. 


Keithley_IP = "169.254.127.39"
BiasHV = -60.0 #in Volt
maxCurrent = 0.001 #in Ampere
"""

from astropix import astropix2
import pandas as pd
import numpy as np
import logging
import binascii
import time 
import os
from modules.pyKeithleyCtl import KeithleySupply as RC
from modules.setup_logger import logger


datadir = "biasscan_weekend_7-15"
psudir = "ps"
digitdir = "digital"

vmin = -10
vmax = -130
vstep = -10

testlen = 6 * 60 * 60

stable_time = 5 * 60

Keithley_IP = "169.254.127.39"
BiasHV = -60.0 #in Volt
maxCurrent = 0.001 #in Ampere


maxlen = 10 * 60 * 60


pspath = datadir + '/' + psudir
csvpath = datadir + '/' + digitdir

basecrrnt = pspath + f"/bias_scan_{vmin}_{vmax}_{vstep}_Source_Ba-133_CURRENTS" + time.strftime("%Y%m%d-%H%M%S")
basedigit = csvpath + f"/bias_scan_{vmin}_{vmax}_{vstep}_Source_Ba-133_DIGITAL" + time.strftime("%Y%m%d-%H%M%S")
basebits = csvpath + f"/bias_scan_{vmin}_{vmax}_{vstep}_Source_Ba-133_BITSTREAMS" + time.strftime("%Y%m%d-%H%M%S")


if os.path.exists(pspath) == False:
    os.makedirs(pspath)
if os.path.exists(csvpath) == False:
    os.makedirs(csvpath)

# This sets the logger name.
logdir = "./runlogs/"
if os.path.exists(logdir) == False:
    os.mkdir(logdir)
logname = "./runlogs/AstropixHVScanlog_" +f"{vmin}_{vmax}_{vstep}_"+ time.strftime("%Y%m%d-%H%M%S") + ".log"

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



def printVoltages(PS):
    print("Set voltage:     ", PS.get_voltage(), "V")
    print("Measured voltage:", PS.measure_voltage(), "V")
    print("Max current:     ", PS.get_ocp()
      , "A")
    print("Measured current:",format((float(PS.measure_current()) * (10**9)), '0.4f'), "nA")


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

        PS.enable_output()
        # Time to stabilize
        logger.info("HV Output on")

        logger.info("set voltage, waiting 5 min")
        time.sleep(stable_time)

        PS.start_measurement(maxlen)    # Turns on HV and starts taking data


        logger.info("HV Logging Start")
        i = 0
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
                        csvframe = pd.concat([csvframe, hits])


    except KeyboardInterrupt:
        logger.info("Recieved Interrupt. Terminating program...")
        returnval = 20
    finally:
        data, nRow = PS.stop_measurement()
        PS.disable_output()
        df = PS.to_csv(data, nRow)
        df["VOLTAGE"] = bias
        df.to_csv(crrntpth)

        # Writes digital data 
        csvframe.index.name = "dec_order"
        csvframe.to_csv(digitpth)
 


    return returnval


def main():
    PS = RC(Keithley_IP)
    PS.clear()
    PS.reset()
    PS.set_voltage(-60)
    PS.set_ocp(maxCurrent)
    printVoltages(PS)

    # Quick check to make sure it is working
    if input("Does this look correct? (Y/n)") == "n":
        PS.disable_output()
        PS.close()

    astro = astropix2(inject=False)
    astro.asic_init()
    astro.init_voltages()
    astro.init_injection()
    astro.enable_spi() 
    logger.info("Chip configured")
    astro.dump_fpga()
    try: # Main loop.
        # Encased in try statement to gaurd against errors
        for bias in range(vmin, vmax + vstep, vstep):
            PS.set_voltage(bias) # sets the bias
            time.sleep(1)
            logger.info(f"HV supply voltage set:{bias}V")
            # Runs the data gathering
            cont = getData(astro, PS, testlen, bias, basecrrnt, basedigit, basebits)
            # checks to make sure it didn't fail
            if cont == 10:
                raise RuntimeError("Maximum errors exceded!")
            if cont == 20:
                raise KeyboardInterrupt
            # Loops again 
        
    except KeyboardInterrupt:
        logger.info("Keyboard interup. Terminating...")

    except Exception as e:
        logger.exception(f"e")
        

    finally: 
        PS.disable_output()
        PS.close()
        astro.close_connection()




if __name__ == "__main__":
    formatter = logging.Formatter('%(asctime)s:%(msecs)d.%(name)s.%(levelname)s:%(message)s')
    fh = logging.FileHandler(logname)
    fh.setFormatter(formatter)
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)

    logging.getLogger().addHandler(sh) 
    logging.getLogger().addHandler(fh)
    logging.getLogger().setLevel(logging.INFO)

    logger = logging.getLogger(__name__)

    main()

