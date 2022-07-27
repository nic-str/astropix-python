"""
Central module of astropix. This incorporates all of the various modules from the original 
The class methods of all the other modules are inherited here. 

Author: Autumn Bauman
"""
# Needed modules. They all import their own suppourt libraries, 
# and eventually there will be a list of which ones are needed to run
from typing import Dict
from modules.spi import Spi 
from modules.nexysio import Nexysio
from modules.decode import Decode
from modules.injectionboard import Injectionboard
from modules.voltageboard import Voltageboard
from bitstring import BitArray
from tqdm import tqdm
import pandas as pd
import regex as re
import binascii
import time

# Logging stuff
import logging
from modules.setup_logger import logger
logger = logging.getLogger(__name__)



# Here are the default configuration values. 
# This includes the DAC configurations, default registers, etc...



class astropix2:
    # First the global defaults which will be used later
    DACS_CFG = {
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
            'vprec': 30,
            'vnrec': 30
        }

    BIAS_CFG = {
            'DisHiDR': 0,
            'q01': 0,
            'qon0': 0,
            'qon1': 1,
            'qon2': 0,
            'qon3': 1,
        }


    # Init just opens the chip and gets the handle. After this runs
    # asic_config also needs to be called to set it up. Seperating these 
    # allows for simpler specifying of values. 
    def __init__(self, clock_period_ns = 10, inject:int = None):
        """
        Initalizes astropix object. 
        No required arguments
        Optional:
        clock_period_ns:int - period of main clock in ns
        inject:bool - if set to True will enable injection for the whole array.
        """

        # _asic_start tracks if the inital configuration has been run on the ASIC yet.
        # By not handeling this in the init it simplifies the function, making it simpler
        # to put in custom configurations and allows for less writing to the chip,
        # only doing it once at init or when settings need to be changed as opposed to 
        # each time a parameter is changed.
        self._asic_start = False
        self.nexys = Nexysio()
        self.handle = self.nexys.autoopen()
        self._wait_progress(2)
        # Ensure it is working
        logger.info("Opened FPGA, testing...")
        self._test_io()
        logger.info("FPGA test successful.")
        # Start putting the variables in for use down the line
        self.sampleclock_period_ns = clock_period_ns
        self.injection_col = inject
        # Creates objects used later on
        self.decode = Decode(clock_period_ns)
        

##################### ASIC METHODS FOR USERS #########################

    # Method to initalize the asic. This is taking the place of asic.py. 
    # All of the interfacing is handeled through asic_update
    def asic_init(self, dac_setup: dict = None, bias_setup:dict = None, digital_mask:str = None, analog_col:int = None):
        """
        self.asic_init() - initalize the asic configuration. Must be called first
        Positional arguments: None
        Optional:
        dac_setup: dict - dictionairy of values passed to the configuration. Only needs values diffent from defaults
        bias_setup: dict - dict of values for the bias configuration Only needs key/vals for changes from default
        digital_mask: str - String of 1s and 0s in 35x35 arangement which masks the array. Needed to enable pixels not (0,0)
        """


        # Now that the asic has been initalized we can go and make this true
        self._asic_start = True
        # The use of update methods on the dictionairy allows for only the keys that 
        # need changing to be passed to the function (hopefully) simplifying the interface
        self.dac_setup = self.DACS_CFG
        if dac_setup is not None:
            self.dac_setup.update(dac_setup)
        self.bias_setup = self.BIAS_CFG
        if bias_setup is not None:
            self.bias_setup.update(bias_setup)

        if digital_mask is not None:
            self._make_digital_mask(digital_mask,analog_col)
        
        self._make_digitalconfig()
        #self._make_digital_mask()
        # Loads it to the chip
        logger.info("LOADING TO ASIC...")
        self.asic_update()
        logger.info("ASIC SUCCESSFULLY CONFIGURED")


    # The method to write data to the asic. Called whenever somthing is changed
    # or after a group of changes are done. Taken straight from asic.py.
    # Might need updating down the line but it should still work
    def asic_update(self):
        """
        Remakes configbits and writes to asic. 
        Takes no input and does not return
        """

        self.nexys.chip_reset()
        asicbits = self.nexys.gen_asic_pattern(self._construct_asic_vector(), True)
        self.nexys.write(asicbits)
        logger.info("Wrote configbits successfully")


    # Methods to update the internal variables. Please don't do it manually
    # This updates the dac config
    def update_asic_config(self, bias_cfg:dict = None, dac_cfg:dict = None, maskstr:str = None, analog_col:int=None):
        """
        Updates and writes confgbits to asic

        bias_cfg:dict - Updates the bias settings. Only needs key/value pairs which need updated
        dac_cfg:dict - Updates DAC settings. Only needs key/value pairs which need updated
        """
        if self.asic_start:
            if bias_cfg is not None:
                self.bias_setup.update(bias_cfg)
            if dac_cfg is not None:
                self.dac_setup.update(dac_cfg)
            if maskstr is not None:
                self._make_digital_mask(maskstr, analog_col)
            else: 
                logger.info("update_asic_config() got no argumennts, nothing to do.")
                return None
            self.asic_update()
        else: raise RuntimeError("Asic has not been initalized")


    def enable_spi(self):
        """
        Starts spi bus. 

        Takes no arguments, returns nothing
        """

        self.nexys.spi_enable()
        self.nexys.spi_reset()
        # Set SPI clockdivider
        # freq = 100 MHz/spi_clkdiv
        self.nexys.spi_clkdiv = 255
        self.nexys.send_routing_cmd()
        logger.info("SPI ENABLED")

    def close_connection(self):
        """
        Terminates the spi bus.
        Takes no arguments. No returns.
        """
        self.nexys.close()


################## Voltageboard Methods ############################

# Here we intitalize the 8 DAC voltageboard in slot 4. dacvals are carried over from past 
# scripts. Default from beam_test.py:
# Use this: (8, [0, 0, 1.1, 1, 0, 0, 1, 1.035])
    def init_voltages(self, slot: int = 4, vcal:float = .989, vsupply: float = 2.7, vthreshold:float = None, dacvals: tuple[int, list[float]] = None):
        """
        Configures the voltage board
        No required parameters. No return.

        slot:int = 4 - Position of voltage board
        vcal:float = 0.908 - Calibration of the voltage rails
        vsupply = 2.7 - Supply Voltage
        vthreshold:float = None - ToT threshold value. Takes precedence over dacvals if set. UNITS: mV
        dacvals:tuple[int, list[float] - vboard dac settings. Must be fully specified if set. 
        """
        # The default values to pass to the voltage dac. Last value in list is threshold voltage, default 100mV or 1.1
        # From nicholas's beam_test.py:
        # 3 = Vcasc2, 4=BL, 7=Vminuspix, 8=Thpix 
        default_vdac = (8, [0, 0, 1.1, 1, 0, 0, 1, 1.100])
        
        # used to ensure this has been called in the right order:
        self._voltages_exist = True

        # Set dacvals
        if dacvals is None:
            dacvals = default_vdac

            # dacvals takes precidence over vthreshold
            if vthreshold is not None:
                # Turns from mV to V with the 1V offset normally present
                vthreshold = (vthreshold/1000) + 1 
                if vthreshold > 1.5 or vthreshold < 0:
                    logger.warning("Threshold voltage out of range of sensor!")
                    if vthreshold <= 0: 
                        vthreshold = 1.100
                        logger.error("Threshold value too low, setting to default 100mV")
                dacvals[1][-1] = vthreshold
        # Create object
        self.vboard = Voltageboard(self.handle, slot, dacvals)
        # Set calibrated values
        self.vboard.vcal = vcal
        self.vboard.vsupply = vsupply
        # Send config to the chip
        self.vboard.update_vb()

    # Here we have the stuff to run injection

    # defaults for the arguments:
    # position: 3
    # dac_settings: (2, [0.4, 0.0])
    # Settings from the orininal scripts
    """
        inj.period = 100
        inj.clkdiv = 400
        inj.initdelay = 10000
        inj.cycle = 0
        inj.pulsesperset = 1
    """
    # Setup Injections
    def init_injection(self, slot: int = 3, inj_voltage:float = None, inj_period:int = 100, clkdiv:int = 300, initdelay: int = 100, cycle: float = 0, pulseperset: int = 1, dac_config:tuple[int, list[float]] = None):
        """
        Configure injections
        No required arguments. No returns.
        Optional Arguments:
        slot: int - Location of the injection module
        inj_voltage: float - Injection Voltage. Range from 0 to 1.8. If dac_config is set inj_voltage will be overwritten
        inj_period: int
        clkdiv: int
        initdelay: int
        cycle: float
        pulseperset: int
        dac_config:tuple[int, list[float]]: injdac settings. Must be fully specified if set. 
        """
        # Default configuration for the dac
        # 0.3 is injection voltage
        # 2 is slot number for inj board
        default_injdac = (2, [0.3, 0.0])
        # Some fault tolerance
        try:
            self._voltages_exist
        except Exception:
            raise RuntimeError("init_voltages must be called before init_injection!")

        # Sets the dac_setup if it isn't specified
        if dac_config is None:
            dac_settings = default_injdac
        else:
            dac_settings = dac_config

        # The dac_config takes presedence over a specified threshold.
        if (inj_voltage is not None) and (dac_config is None):
            # elifs check to ensure we are not injecting a negative value because we don't have that ability
            if inj_voltage < 0:
                raise ValueError("Cannot inject a negative voltage!")
            elif inj_voltage > 1800:
                logger.warning("Cannot inject more than 1800mV, will use defaults")
            else:
                #Convert from mV to V
                inj_voltage = inj_voltage / 1000
                dac_settings[1][0] = inj_voltage

        # Create the object!
        self.inj_volts = Voltageboard(self.handle, slot, dac_settings)
        # set the parameters
        self.inj_volts.vcal = self.vboard.vcal
        self.inj_volts.vsupply = self.vboard.vsupply
        self.inj_volts.update_vb()
        # Now to configure the actual injection thing
        self.injector = Injectionboard(self.handle)
        # Now to configure it. above are the values from the original scripting.
        self.injector.period = inj_period
        self.injector.clkdiv = clkdiv
        self.injector.initdelay = initdelay
        self.injector.cycle = cycle
        self.injector.pulsesperset = pulseperset       

    # These start and stop injecting voltage. Fairly simple.
    def start_injection(self):
        """
        Starts Injection.
        Takes no arguments and no return
        """
        self.injector.start()
        logger.info("Began injection")

    def stop_injection(self):
        """
        Stops Injection.
        Takes no arguments and no return
        """
        self.injector.stop()
        logger.info("Stopped injection")


########################### Input and Output #############################
    # This method checks the chip to see if a hit has been logged

    def hits_present(self):
        """
        Looks at interrupt
        Returns bool, True if present
        """
        if (int.from_bytes(self.nexys.read_register(70),"big") == 0):
            return True
        else:
            return False

    def get_log_header(self):
        """
        Returns header for use in a log file with all settings.
        """
        # This is not a nice line, but its the most efficent way to get all the values in the same place.
        return f"Voltageboard settings: {self.vboard.dacvalues}\n" + f"Digital: {self.digitalconfig}\n" +f"Biasblock: {self.bias_setup}\n" + f"DAC: {self.dac_setup}\n" + f"Receiver: {self.recconfig}\n"


############################ Decoder Stuffs ##############################
    # This function generates a list of the hits in the stream. Retuerns a bytearray

    def get_readout(self, bufferlength:int = 20):
        """
        Reads hit buffer.
        bufferlength:int - length of buffer to write. Multiplied by 8 to give number of bytes
        Returns bytearray
        """
        self.nexys.write_spi_bytes(bufferlength)
        readout = self.nexys.read_spi_fifo()
        return readout


    def decode_readout(self, readout:bytearray, i:int, printer: bool = True):
        """
        Decodes readout

        Required argument:
        readout: Bytearray - readout from sensor, not the printed Hex values
        i: int - Readout number

        Optional:
        printer: bool - Print decoded output to terminal

        Returns dataframe
        """

        list_hits = self.decode.hits_from_readoutstream(readout)
        hit_list = []
        for hit in list_hits:
            # Generates the values from the bitstream
            id          = int(hit[0]) >> 3
            payload     = int(hit[0]) & 0b111
            location    = int(hit[1])  & 0b111111
            col         = 1 if (int(hit[1]) >> 7 ) & 1 else 0
            timestamp   = int(hit[2])
            tot_msb     = int(hit[3]) & 0b1111
            tot_lsb     = int(hit[4])   
            tot_total   = (tot_msb << 8) + tot_lsb

            wrong_id        = 0 if (id) == 0 else '\x1b[0;31;40m{}\x1b[0m'.format(id)
            wrong_payload   = 4 if (payload) == 4 else'\x1b[0;31;40m{}\x1b[0m'.format(payload)   

                
            
            # will give terminal output if desiered
            if printer:
                print(
                f"{i} Header: ChipId: {wrong_id}\tPayload: {wrong_payload}\t"
                f"Location: {location}\tRow/Col: {'Col' if col else 'Row'}\t"
                f"Timestamp: {timestamp}\t"
                f"ToT: MSB: {tot_msb}\tLSB: {tot_lsb} Total: {tot_total} ({(tot_total * self.sampleclock_period_ns)/1000.0} us)"
            )
            # hits are sored in dictionairy form
            # Look into dataframe
            hits = {
                'readout': i,
                'Chip ID': id,
                'payload': payload,
                'location': location,
                'isCol': (True if col else False),
                'timestamp': timestamp,
                'tot_msb': tot_msb,
                'tot_lsb': tot_lsb,
                'tot_total': tot_total,
                'tot_us': ((tot_total * self.sampleclock_period_ns)/1000.0),
                'hittime': time.time()
                }
            hit_list.append(hits)

        # Much simpler to convert to df in the return statement vs df.concat
        return pd.DataFrame(hit_list)

    # To be called when initalizing the asic, clears the FPGAs memory 
    def dump_fpga(self):
        """
        Reads out hit buffer and disposes of the output.

        Does not return or take arguments. 
        """
        readout = self.get_readout()
        del readout








###################### INTERNAL METHODS ###########################

# Below here are internal methods used for constructing things and testing

    # _test_io(): A function to read and write a register on the chip to see if 
    # everythign is working. 
    # It takes no arguments 

    def _test_io(self):
        try:    # Attempts to write to and read from a register
            self.nexys.write_register(0x09, 0x55, True)
            self.nexys.read_register(0x09)
            self.nexys.spi_reset()
            self.nexys.sr_readback_reset()
        except Exception: 
            raise RuntimeError("Could not read or write from astropix!")
    
    # _make_digitalconfig(): Constructs the digitalconfig dictionairy. 
    # Takes no arguments currently, and there is no way to update 
    # self.digitalconfig (yet). Those might be added down the line 

    def _make_digitalconfig(self):
        # This can probably be replaced with a dictionairy comprehension. 
        # I put this into for loops so we can use the range function which 
        # makes it a lot easier to see whats going on
        self.digitalconfig = {'interupt_pushpull': 1}
        for i in range(1,19):
            self.digitalconfig[f"En_Inj{i}"] = 0
        self.digitalconfig["ResetB"] = 0
        for i in range(0,8):
            self.digitalconfig[f'Extrabit{i}'] = 1
        for i in range(8,15):
            self.digitalconfig[f'Extrabit{i}'] = 0

    # Function to construct the reconfig dictionairy. This code is taken from 
    # asic.py. 

    # used for digital working with the sensor.

    def _make_digital_mask(self, digitmask:str, analog_col=None):
        # Cleans up the string, ensures it is only 1, 0, or \n
        bitmask = re.sub("[^01\n]", "", digitmask)
        # turn it into a list
        bitlist = bitmask.split("\n")
        # Remove any extra rows that creeped in
        if len(bitlist) > 35:
            bitlist = bitlist[0:35]
        # The dictionairy which is returned
        self.recconfig = {}
        # used in construction
        i = 0
        # iterates through the list and does binary magic on it
        for bits in bitlist:
            # This works by adding entries to a dictionary and then:
            # 1) creating a 35 bit space of zeros
            # 2) converting the string to a binary integer
            # 3) shifting by one to make room for injection on/off bit
            # 4) setting the injection bit if we want injection on this run
            # Bit 1: Analog output
            # Bit 2: Injection
            # last : Injection
            analog_bit = 0b1 if (i == analog_col) else 0
            injection_bit = 0b1 if (i == self.injection_col) else 0
            self.recconfig[f"ColConfig{i}"] = (analog_bit << 37) + (injection_bit << 36) + (int(bits, 2) << 1) + injection_bit
            i += 1



    # This is from asic.py, and it essentially takes all the parameters and puts
    # them into a form ready to be loaded onto the board.
    # Parameters: msbfirst: Send vector MSB first
    
    def _construct_asic_vector(self, msbfirst:bool = False):
        bitvector = BitArray()

        for value in self.digitalconfig.values():
            bitvector.append(self.__int2nbit(value, 1))

        for value in self.bias_setup.values():
            bitvector.append(self.__int2nbit(value, 1))

        for value in self.dac_setup.values():
            bitvector.append(self.__int2nbit(value, 6))

        for value in self.recconfig.values():
            bitvector.append(self.__int2nbit(value, 38))

        if not msbfirst:
            bitvector.reverse()

        # print(f'Bitvector: {bitvector} \n')

        return bitvector      
    def __int2nbit(self,value: int, nbits: int) -> BitArray:
        """Convert int to 6bit bitarray

        :param value: DAC value 0-63
        """

        try:
            return BitArray(uint=value, length=nbits)
        except ValueError:
            print(f'Allowed Values 0 - {2**nbits-1}')

    # A progress bar! So facny I know 
    def _wait_progress(self, seconds:int):
        for _ in tqdm(range(seconds), desc=f'Wait {seconds} s'):
            time.sleep(1)
