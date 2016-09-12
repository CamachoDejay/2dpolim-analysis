import sys
import numpy as np
from util2dpolim.movie import Movie
from util2dpolim.misc import * # save_hdf5, save_spot_hdf5, remove_hdf5_files, pixel_list, import_spot_positions
import time as stopwatch



#### data directory and file name ####

prefix = '/home/rafa/Desktop/share/2DMEH-PPV/SMmode'
basename = 'bdm8area10'

SNR        = 1.0
VFR        = .4
spotradius = 4  # pixel
blankfit   = True    # True 
exclusion_bf = [45,85,420,495] 





m = Movie( prefix, basename )
m.find_portraits( frameoffset=0 )
m.find_lines()


#### blank fitting ####
if blankfit:
    boolimage = np.ones( (m.sample_data.rawdata.shape[1],m.sample_data.rawdata.shape[2]), dtype=np.bool )*True
    blankfitexclusion = {'left':exclusion_bf[0], 'right':exclusion_bf[2],
                                     'upper':exclusion_bf[1], 'lower':exclusion_bf[3], 'op':'exclude'}
    boolimage = pixel_list( m, blankfitexclusion, boolimage )
    m.fit_blank_image( boolimage, verbosity=0 )

#### main part of the analysis #### This next line takes care of BG definition due to use_borderbg
import_spot_positions( m, prefix,  basename, spotradius, 'circle', use_borderbg=True )

m.correct_excitation_intensities()
m.correct_emission_intensities()
m.are_spots_valid( SNR=SNR, validframesratio=VFR )

if not len(m.validspots)==0:
    print len(m.validspots)
    tstart = stopwatch.time()

    #### decide which part of the analysis you want done here ###

    # multi-proc (Linux only):
    # m.run_mp( Nprocs=Nprocs, fits=True, mods=True, ETruler=True, ETmodel=True )

    # single-core:
    # first step is to fit cosine functions to the portrait
    m.fit_all_portraits_spot_parallel_selective( range(len(m.validspots)) )
    # the second step is to find the modulation depths and other classical parameters from the fitted portraits
    m.find_modulation_depths_and_phases_selective( range(len(m.validspots)) )
    for s in m.validspots:
        s.values_for_ETruler( newdatalength=1024 )
    m.ETmodel_selective( range(len(m.validspots)) )

#### save output to hdf5 ####
# For sm data, we don't update, but replace hdf5 files.
# So we delete first,
remove_hdf5_files( m )    
# and then write the new ones:
save_spot_hdf5( m )
save_hdf5( m )

# we're done here






