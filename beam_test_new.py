"""
Updated version of beam_test.py using the astropix.py module
"""

from astropix import astropix2
import datetime
import time
import csv

filedir = "./data/"

filebase = "test_on_"

inj_runup = 10

max_errors = 1 # limit of how many decde index errors are allowed in a row

mask_file = "./testdat/mask.txt"

#Init stuffs
def main(inj:bool = False, ToT:float = 100):
    astro = astropix2(inj)
    astro.asic_init()
    astro.init_voltages(4, .908, 2.7, 1.1)
    #if inj: astro.init_injection()
    astro.enable_spi()
    
    print("CONFIGURATION SUCCESSFUL")


    filepath = filedir + filebase + datetime.strftime('%Y.%m.%d-%h:%m:%s') + '.csv'
    csv_header = [    
                'timestamp',
                'global_time'
                'Chip ID',
                'payload',
                'location',
                'row/col',
                'tot_total',
                'tot_ns',
                'hitbits'
                ]

    with open(filepath, 'w') as file:
        #file.write("globaltime, timestamp, chip_time, location, rowcol, tot_total, tot_time\n")
        writer = csv.DictWriter(file, csv_header, extrasaction='ignore')
        writer.writeheader()
        astro.start_injection()
        astro.dump_fpga()



        errors = 0 # Sets 
        i = 0
        try:
            while (errors < max_errors):
                if astro.hits_present():
                    time.sleep(.5)
                    readout = astro.get_readout()
                    try:
                        hits = astro.decode_readout(printer = True)
                    except IndexError:
                        errors += 1
                        continue
                    # This gives time since epoch to help standardize data across all systems 
                    timenow = time.time()
                    # Here we itterate over the list of hits and add the timestamp to the dictionairies 
                    for i in range(len(hits) - 1):
                        hits[i]['global_time'] = timenow
                    # Takes the list of hits and itterativey writes them all to the csv output
                    writer.writerows(hits)
                    i += 1
                else: time.sleep(.5)
        except KeyboardInterrupt:
            astro.close()

if __name__ == "__main__":
    main()