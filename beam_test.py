"""
Updated version of beam_test.py using the astropix.py module

Author: Autumn Bauman 
"""

#from msilib.schema import File
from astropix import astropix2
import modules.hitplotter as hitplotter
import binascii
import datetime
import pandas as pd
import numpy as np
import time
import logging
import argparse

from modules.setup_logger import logger



logger = logging.getLogger(__name__)
  

#Init stuffs
def main(args):

    # Used for creating the mask
    masked = False
    if args.mask is not None:
        masked = True
        with open(args.mask, 'r') as file:
            bitmask = file.read()

    # Prepare everything, create the object
    astro = astropix2(inject=args.inject)

    # Passes mask if specified, else it creates an analog mask of (0,0)
    if masked: 
        astro.asic_init(digital_mask=bitmask)
    else: 
        astro.asic_init()

    astro.init_voltages(vthreshold=args.threshold)
    # If injection is on initalize the board
    if args.inject:
        astro.init_injection(inj_voltage=args.vinj)
    astro.enable_spi() 
    logger.info("Chip configured")
    astro.dump_fpga()

    if args.inject:
        astro.start_injection()

    max_errors = args.errormax
    i = 0
    errors = 0 # Sets the threshold 

    # Prepares the file paths 
    if args.saveascsv: # Here for csv
        csvpath = args.outdir + args.name + '_' + datetime.datetime.strftime("%Y%m%d-%H%M%S") + '.csv'

    # And here for the text files/logs
    logpath = args.outdir + args.name + '_' + datetime.datetime.strftime("%Y%m%d-%H%M%S") + '.log'

    # textfiles are always saved so we open it up 
    logfile = open(logpath,'w')

    # Writes all the config information to the file
    logfile.write(astro.get_log_header())

    # Enables the hitplotter and uses logic on whether or not to save the images
    if args.showhits: plotter = hitplotter.HitPlotter(35, outdir=args.outdir if args.plotsave else None)

    try: # By enclosing the main loop in try/except we are able to capture keyboard interupts cleanly

        while True: #This loop doesn't need to use any conditional logic as all the exit cases are easier to handle with 
            # This might be possible to do in the loop declaration, but its a lot easier to simply add in this logic
            if args.maxhits is not None:
                if i >= args.maxhits: break
            
            if astro.hits_present(): # Checks if hits are present
                time.sleep(.1) # this is probably not needed, will ask Nick
                readout = astro.get_readout() # Gets the bytearray from the chip
                # Writes the hex version to hits
                logfile.write(f"{i}\t{str(binascii.hexlify(readout))}\n")
                # Added fault tolerance for decoding, the limits of which are set through arguments
                try:
                    hits = astro.decode_readout(readout, i, printer = True)
                except IndexError:
                    errors += 1
                    logger.error(f"Decoding failed. Failure {errors} of {max_errors} on readout {i}")
                    # If it has errored out, this will exit the loop and program
                    if errors > max_errors:
                        logger.critical(f"Decoding failed {errors} times on an index error. Terminating Progam...")
                        break
                    
                    continue
                # If we are saving a csv this will write it out. 
                if args.saveascsv:
                    # Since we need the header only on the first hit readout this opens it in write mode first with header set true
                    # and for all times after set false and append mode
                    with open(csvpath, 'a' if i != 0 else 'w') as csvfile:
                        hits.to_csv(
                            csvfile, 
                            header=False if i!=0 else True
                            )
                        csvfile.write('\n')

                # This handels the hitplotting. Code by Henrike and Amanda
                if args.showhits:
                    rows,columns=[],[]
                    if len(hits)>0:#safeguard against bad readouts without recorded decodable hits
                        #Isolate row and column information from array returned from decoder
                        location = hits.location.to_numpy()
                        rowOrCol = hits.rowcol.to_numpy()
                        rows = location[rowOrCol==0]
                        columns = location[rowOrCol==1]
                    plotter.plot_event( rows, columns, i)
                # Increments the run counter
                i += 1
            # If no hits are present this waits for some to accumulate
            else: time.sleep(.1)



    # Ends program cleanly when a keyboard interupt is sent.
    except KeyboardInterrupt:
        logger.critical("Keyboard interupt. Program halt!")
    
    logfile.close() # Close open file
    if args.inject: astro.stop_injection()   #stops injection
    astro.close() # Closes SPI
    logger.info("Program terminated")
    # END OF PROGRAM


    

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Astropix Driver Code')
    parser.add_argument('-n', '--name', default='', required=False,
                    help='Option to give extra name to output files upon running')

    parser.add_argument('-o', '--outdir', default='.', required=False,
                    help='Output Directory')

    parser.add_argument('-s', '--showhits', action='store_true',
                    default=False, required=False,
                    help='Display hits in real time during data taking')
    
    parser.add_argument('-p', '--plotsave', action='store_true', default=False, required=False,
                    help='Save plots as image files. DEFAULT FALSE')
    
    parser.add_argument('-c', '--saveascsv', action='store_true', 
                    default=False, required=False, 
                    help='save output files as CSV. If False, save as txt')
    
    parser.add_argument('-i', '--inject', action='store_true',default=False,
                    help =  'Toggle injection on and off. DEFAULT: OFF')

    parser.add_argument('-v','--vinj', action='store', default = 0.4, type=float,
                    help = 'Specify injection voltage. DEFAULT 0.4V')

    parser.add_argument('-m', '--mask', action='store', required=False, type=str, default = None,
                    help = 'filepath to digital mask. Required to enable pixels not (0,0)')

    parser.add_argument('-t', '--threshold', type = float, action='store', default=None,
                    help = 'Threshold voltage for digital ToT (in mV). DEFAULT 100mV')
    
    parser.add_argument('-E', '--errormax', action='store', type=int, default='0', 
                    help='Maximum index errors allowed during decoding. DEFAULT 0')

    parser.add_argument('-M', '--maxruns', type=int, action='store', default=None,
                    help = 'Maximum number of readouts')
    
    parser.add_argument
    args = parser.parse_args()
    
    main(args)