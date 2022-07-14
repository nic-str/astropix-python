import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Astropix Driver Code')
    parser.add_argument('-n', '--name', default='', required=False,
                    help='Option to give extra name to output files upon running')

    parser.add_argument('-o', '--outdir', default='.', required=False,
                    help='Output Directory for all datafiles')

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

    parser.add_argument('-v','--vinj', action='store', default = 400, type=float,
                    help = 'Specify injection voltage (in mV). DEFAULT 400 mV')

    parser.add_argument('-m', '--mask', action='store', required=False, type=str, default = None,
                    help = 'filepath to digital mask. Required to enable pixels not (0,0)')

    parser.add_argument('-t', '--threshold', type = float, action='store', default=None,
                    help = 'Threshold voltage for digital ToT (in mV). DEFAULT 100mV')
    
    parser.add_argument('-E', '--errormax', action='store', type=int, default='0', 
                    help='Maximum index errors allowed during decoding. DEFAULT 0')

    parser.add_argument('-M', '--maxruns', type=int, action='store', default=None,
                    help = 'Maximum number of readouts')

    parser.add_argument('--timeit', action="store_true", default=False,
                    help='Prints runtime from seeing a hit to finishing the decode to terminal')

    args = parser.parse_args()
    
    print(args)