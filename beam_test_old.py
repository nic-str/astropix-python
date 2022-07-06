# -*- coding: utf-8 -*-
""""""
"""
Created on Sat Jun 26 00:10:56 2021

@author: Nicolas Striebig
"""

from modules.asic import Asic
from modules.injectionboard import Injectionboard
from modules.nexysio import Nexysio
from modules.voltageboard import Voltageboard
from modules.decode import Decode

from utils.utils import wait_progress

import binascii

import os
import time

def main():

    nexys = Nexysio()

    # Open FTDI Device with Index 0
    #handle = nexys.open(0)
    handle = nexys.autoopen()

    # Write and read directly to register
    # Example: Write 0x55 to register 0x09 and read it back
    nexys.write_register(0x09, 0x55, True)
    nexys.read_register(0x09)

    nexys.spi_reset()
    nexys.sr_readback_reset()

    #
    # Configure ASIC
    #

    # Write to asicSR
    asic = Asic(handle)
    asic.update_asic()

    # Example: Update Config Bit
    # asic.digitalconfig['En_Inj17'] = 1
    # asic.dacs['vn1'] = 63
    # asic.update_asic()

    #
    # Configure Voltageboard
    #

    # Configure 8 DAC Voltageboard in Slot 4 with list values
    # 3 = Vcasc2, 4=BL, 7=Vminuspix, 8=Thpix
    vboard1 = Voltageboard(handle, 4, (8, [0, 0, 1.1, 1, 0, 0, 1, 1.1]))

    # Set measured 1V for one-point calibration
    vboard1.vcal = 0.989
    vboard1.vsupply = 3.3

    # Update voltageboards
    vboard1.update_vb()

    # Write only first 3 DACs, other DACs will be 0
    # vboard1.dacvalues = (8, [1.2, 1, 1])
    # vboard1.update_vb()

    #
    # Configure Injectionboard
    #

    # Set Injection level
    injvoltage = Voltageboard(handle, 3, (2, [0.4, 0.0]))
    injvoltage.vcal = vboard1.vcal
    injvoltage.vsupply = vboard1.vsupply
    injvoltage.update_vb()

    inj = Injectionboard(handle)

    # Set Injection Params for 330MHz patgen clock
    inj.period = 100
    inj.clkdiv = 400
    inj.initdelay = 10000
    inj.cycle = 0
    inj.pulsesperset = 1

    #
    # SPI
    #

    # Enable SPI
    nexys.spi_enable()
    nexys.spi_reset()

    # Set SPI clockdivider
    # freq = 100 MHz/spi_clkdiv
    nexys.spi_clkdiv = 255

    #asic.dacs['vn1'] = 5

    # Generate bitvector for SPI ASIC config
    asic_bitvector = asic.gen_asic_vector()
    spi_data = nexys.asic_spi_vector(asic_bitvector, True, 10)

    # Write Config via spi
    # nexys.write_spi(spi_data, False, 8191)

    # Send Routing command
    nexys.send_routing_cmd()

    # Reset SPI Read FIFO

    #inj.start()
    inj.stop()

    wait_progress(3)

    #decode = Decode()

    
    """ i = 0
    while os.path.exists("log/sample%s.log" % i):
        i += 1

    file = open("log/sample%s.log" % i, "w") """
    timestr = time.strftime("beam_%Y%m%d-%H%M%S")
    file = open("log/%s.log" % timestr, "w")
    file.write(f"Voltageboard settings: {vboard1.dacvalues}\n")
    file.write(f"Digital: {asic.digitalconfig}\n")
    file.write(f"Biasblock: {asic.biasconfig}\n")
    file.write(f"DAC: {asic.dacs}\n")
    file.write(f"Receiver: {asic.recconfig}\n")

    readout = bytearray()

    while True:
        print("Reg: {}", int.from_bytes(nexys.read_register(70),"big"))
        if(int.from_bytes(nexys.read_register(70),"big") == 0):
            time.sleep(0.1)
            nexys.write_spi_bytes(20)
            readout = nexys.read_spi_fifo()
            file.write(str(binascii.hexlify(readout)))

            print(binascii.hexlify(readout))

            #decode.decode_astropix2_hits(decode.hits_from_readoutstream(readout))

    # inj.stop()

    # Close connection
    nexys.close()


if __name__ == "__main__":
    main()
