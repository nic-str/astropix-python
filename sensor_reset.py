"""
Code to cleanly power cycle sensor remotely

Driver code: Autumn
Nexys code: Nicolas
"""

from modules.nexysio import Nexysio

# This is the driver code to do this 

nexys = Nexysio()
handle = nexys.autoopen()

nexys.chip_reset()

# This may or may not work, or it could cause issues. I will comment it out if needed.
nexys.close()