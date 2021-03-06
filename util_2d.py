import numpy as np
import matplotlib.pyplot as plt
plt.interactive(1)
from files import MyPrincetonSPEFile
from motors import NewSetupMotor, ExcitationMotor, EmissionMotor, BothMotors
from fitting import CosineFitter, CosineFitter_new, CosineFitter_mpi_master
import scipy.optimize as so


class Movie:
    def __init__2(self, \
                      datadir, filename, \
                      which_setup='new setup', \
                      phase_offset_excitation=0, \
                      excitation_optical_element='l/2 plate',\
                  ):

        self.cos_fitter = CosineFitter_new
        self.which_setup = which_setup
        self.phase_offset_excitation = phase_offset_excitation

        self.data_directory = datadir
        self.data_filename  = filename

        self.read_in_EVERYTHING()

        self.timeaxis = self.camera_data.timestamps
        self.spots = []
        self.initContrastImages()
        self.datamode = 'validdata'

        # fix the excitation and emission angle grids for now
        self.excitation_angles_grid = np.linspace(0,np.pi,91)
        self.emission_angles_grid = np.linspace(0,np.pi,91)
        self.Nphases_for_cos_fitter = 91
        self.precomputed_cosines = [ np.cos(2*(self.emission_angles_grid-ph)) \
                                         for ph in np.linspace(0,np.pi/2,self.Nphases_for_cos_fitter) ]


    def __init__( self, \
                      spe_filename, \
                      excitation_motor_filename, \
                      emission_motor_filename=None, \
                      blank_sample_filename=None, \
                      phase_offset_excitation=0, \
                      datamode='validdata', \
                      which_setup='new setup', \
                      use_new_fitter=True, \
                      excitation_optical_element='L/2 plate'):        

        # if not blank_sample_filename==None:
        #     self.blank_sample = CameraData( blank_sample_filename )

        self.camera_data    = CameraData( spe_filename, compute_frame_average=True )

        if use_new_fitter:
            self.cos_fitter = CosineFitter_new
        else:
            self.cos_fitter = CosineFitter

        self.which_setup = which_setup
            
        # set up motors --- phase offset in radians!!!
        if which_setup=='old setup':
            self.excitation_motor = ExcitationMotor( excitation_motor_filename, \
                                                         phase_offset_excitation, \
                                                         rotation_direction=-1, \
                                                         optical_element=excitation_optical_element)
            self.emission_motor   = EmissionMotor( emission_motor_filename )

        elif which_setup=='new setup':
            self.excitation_motor = NewSetupMotor( excitation_motor_filename, \
                                                       which_motor='excitation', \
                                                       phase_offset=phase_offset_excitation, \
                                                       optical_element=excitation_optical_element )
            if emission_motor_filename==None:
                emission_motor_filename = excitation_motor_filename
            self.emission_motor = NewSetupMotor( emission_motor_filename, \
                                                     which_motor='emission', \
                                                     phase_offset=0*np.pi/180.0 )
        elif which_setup=='cool new setup':
            self.motors = BothMotors( excitation_motor_filename, \
                                          phase_offset_excitation, \
                                          optical_element=excitation_optical_element )
        else:
            raise hell

        # where do we get our time axis from?  
        self.timeaxis = self.camera_data.timestamps

        # init list of spots
        self.spots = []

        # init contrast images
        self.initContrastImages()

        # store phase offset
#        self.phase_offset_excitation = phase_offset_excitation
        # set data mode, used by collect_data() and startstop()
        self.datamode = datamode

        # fix the excitation and emission angle grids for now
        self.excitation_angles_grid = np.linspace(0,np.pi,91)
        self.emission_angles_grid = np.linspace(0,np.pi,91)
        self.Nphases_for_cos_fitter = 91
        self.precomputed_cosines = [ np.cos(2*(self.emission_angles_grid-ph)) \
                                         for ph in np.linspace(0,np.pi/2,self.Nphases_for_cos_fitter) ]


    def read_in_EVERYTHING(self):
        # change to the data directory
        os.chdir( self.data_directory )

        ###### look for motor files ######
        print 'Looking for motor file(s)...'
        got_motors = 0
        # new setup file
        for file in os.listdir("."):
            if file=="MS-"+self.data_filename[:-4]+'.txt':
                print '\t found motor file %s' % file
                self.which_setup = 'new'
                self.motorfile = file
                # import it
                self.motors = BothMotorsWithHeader( file )
                self.exangles = self.motors.excitation_angles
                self.emangles = self.motors.emission_angles

                got_motors = True
                break


        # old setup files   ########## TODO: All motor files should be the same --> fix in LabView
        got_motor_file_ex = 0
        got_motor_file_em = 0
        if not got_motors:
            for file in os.listdir("."):
                if file=="MSex-"+self.data_filename[:-4]+'.txt':
                    print '\t found old-style motor file (for excitation) %s' % file
                    self.which_setup = 'old'
                    self.motorfile_ex = file
                    # read in motor file
                    if self.which_setup=='new setup':
                        self.excitation_motor = NewSetupMotor( file, \
                                                       which_motor='excitation', \
                                                       phase_offset=self.phase_offset_excitation, \
                                                       optical_element=self.excitation_optical_element )
                    elif which_setup=='old setup':
                        self.excitation_motor = ExcitationMotor( file, \
                                                                     self.phase_offset_excitation, \
                                                                     rotation_direction=-1, \
                                                                     optical_element=self.excitation_optical_element)
                    else:
                        raise hell

                    self.exangles = np.array( [self.excitation_motor.angle(t,exposuretime=self.camera_data.exposuretime) for t in self.timeaxis] )

                    got_motor_file_ex = 1
                    if got_motor_file_ex and got_motor_file_em:
                        got_motors = True
                        break
                if file=="MSem-"+self.data_filename[:-4]+'.txt':
                    print '\t found old-style motor file (for emission) %s' % file
                    self.which_setup = 'old'
                    self.motorfile_em = file
                    # read in motor file
                    if self.which_setup=='new setup':
                        self.emission_motor = NewSetupMotor( file, \
                                                                 which_motor='emission', \
                                                                 phase_offset=0*np.pi/180.0 )
                    elif self.which_setup=='old setup':
                        self.emission_motor   = EmissionMotor( emission_motor_filename )
                    else:
                        raise hell

                    emangles = np.array( [self.emission_motor.angle(t,exposuretime=self.camera_data.exposuretime) for t in self.timeaxis] )

                    got_motor_file_em = 1
                    if got_motor_file_ex and got_motor_file_em:
                        got_motors = True
                        break


        ###### look if we can find the data file, and import it ######
        if os.path.exists( self.data_filename ):
            self.camera_data    = CameraData( self.data_filename, compute_frame_average=True )
            print 'Imported data file %s' % self.data_filename
        else:
            print "Couldn't find data SPE file! Bombing out..."
            raise SystemExit
        
        ###### look for blank sample ######
        print 'Looking for blank...',
        for file in os.listdir("."):
            if file.startswith("blank-") and (file.endswith(".spe") or file.endswith(".SPE")):
                print '\t found file %s' % file
                b = CameraData( file, compute_frame_average=True )
                self.blank = b.average_image.copy()
                del(b)
                break


    def initContrastImages(self):
        self.spot_coverage_image  = np.ones( (self.camera_data.datasize[1],self.camera_data.datasize[2]) )*np.nan
        self.mean_intensity_image = self.spot_coverage_image.copy()
        self.SNR_image            = self.spot_coverage_image.copy()
        self.M_ex_image           = self.spot_coverage_image.copy()
        self.M_em_image           = self.spot_coverage_image.copy()
        self.phase_ex_image       = self.spot_coverage_image.copy()
        self.phase_em_image       = self.spot_coverage_image.copy()
        self.LS_image             = self.spot_coverage_image.copy()
        self.ET_ruler_image       = self.spot_coverage_image.copy()
        self.ET_model_md_fu_image = self.spot_coverage_image.copy()
        self.ET_model_th_fu_image = self.spot_coverage_image.copy()
        self.ET_model_gr_image    = self.spot_coverage_image.copy()
        self.ET_model_et_image    = self.spot_coverage_image.copy()


    def define_background_spot( self, coords, intensity_type='mean' ):
        # create new spot object
        s = Spot( self.camera_data.rawdata, coords, bg=0, int_type=intensity_type, \
                      label='background area', is_bg_spot=True, parent=self )
        self.bg_spot = s        

        # if blank data is present, automatically work out its bg, correct for it,
        # and compute average blank image
        if hasattr(self, 'blanks'):
            # init a blank image
            self.blank_image = np.zeros_like(self.blanks[0])
            # go through all blanks
            for b in self.blanks:
                # get that background spot
                s = Spot( b.resize((1,b.shape[0],b.shape[1])), coords, bg=0, int_type=intensity_type, \
                              label='background area', is_bg_spot=True, parent=self )
                # add bg-corrected blank to blank_image
                self.blank_image += b-s.I
            # divide blank image by number of blanks
            self.blank_image /= len(self.blanks)

        # record background spot in spot coverage image
        self.spot_coverage_image[ s.coords[1]:s.coords[3]+1, s.coords[0]:s.coords[2]+1 ] = -1
        

    def define_spot( self, coords, intensity_type='mean', label=None ):
        """Defines a new spot object and adds it to the list.
        FIXME: make sure coordinate definitions do not exceed frame size
        TO-DO: how about being able to specify center+radius ?
        """

        if hasattr( self, 'bg_spot' ):
            bgself = self.bg_spot.intensity
        else:
            bgself = 0
                
        if hasattr( self, 'blank_image' ):
            bgblank=True
        else:
            bgblank=False

        # create new spot object
        s = Spot( self.camera_data.rawdata, coords, bg=bgself, int_type='mean', \
                      label=label, parent=self, blankdata=bgblank )
        # append spot object to spots list
        self.spots.append( s )

        self.spot_coverage_image[ s.coords[1]:s.coords[3]+1, s.coords[0]:s.coords[2]+1 ] = 1
        self.mean_intensity_image[ s.coords[1]:s.coords[3]+1, s.coords[0]:s.coords[2]+1 ] = s.mean_intensity

    def collect_data( self ):
        """This is a helper-function which collects all the necessary 
        information for further analysis in one array.

        Outputs:
        If mode is 'truedata' then an array with columns:
        [FrameNumber, Validity, excitation angle, emission angle, Intensities (Nspot columns)]
        If mode is 'validdate' then:
        [FrameNumber, excitation angle, emission angle, Intensities (Nspot columns)]    
        """

        if self.which_setup=='cool new setup':
            exangles = self.motors.excitation_angles
            emangles = self.motors.emission_angles
        else:
            exangles = np.array( [self.excitation_motor.angle(t,exposuretime=self.camera_data.exposuretime) \
                                      for t in self.timeaxis] )
            emangles = np.array( [self.emission_motor.angle(t,exposuretime=self.camera_data.exposuretime) \
                                      for t in self.timeaxis] )
        validframes = emangles != -1
        self.Nvalidframes = np.sum(validframes)

        Intensity = np.zeros( (self.timeaxis.size, len(self.spots)) )
        for i,s in enumerate(self.spots):
            Intensity[:,i] = self.spots[i].intensity
#            self.spots[i].mean_intensity = np.mean( self.spots[i].intensity )
            del( self.spots[i].intensity )

        # if Intensity.ndim==1:
        #     Nspots = 1
        #     Intensity = Intensity.reshape( (Intensity.size,1) )
        # elif Intensity.ndim>2:
        #     raise hell
        # else:
        #     Nspots = Intensity.shape[1]

        Nspots = Intensity.shape[1]

        # make sure that shapes of Intensity and timeaxis match
        assert Intensity.shape[0] == self.timeaxis.size    ### FIXME: is this still needed?

        if self.datamode=='truedata':
            exangles = np.round(exangles, decimals=2)
            emangles = np.round(emangles, decimals=2)

            output = np.zeros( (self.timeaxis.size, 4+Nspots) )
            for i in range( self.timeaxis.size ):
                output[i,0] = i
                output[i,1] = np.int( validframes[i] )
                output[i,2] = exangles[i]
                output[i,3] = emangles[i]
                output[i,4:4+Nspots] = Intensity[i,:]

        elif self.datamode=='validdata':
            emangles = np.round(emangles[validframes], decimals=2)
            exangles = np.round(exangles[validframes], decimals=2)

#            print emangles.shape

            output = np.zeros( (self.Nvalidframes, 3+Nspots) )
            trueindices = validframes.nonzero()[0]
            for i in range( self.timeaxis[validframes].size ):            
                output[i,0] = trueindices[i]
                output[i,1] = exangles[i]
                output[i,2] = emangles[i]
                output[i,3:3+Nspots] = Intensity[trueindices[i],:]
        else:
            raise ValueError("Don't understand datamode: %s" % (self.datamode))
                
        self.data = output


    def startstop( self ):
        """
        This function determines the indices at which portraits start and end.
        There's a fair bit of hackery in here, and to understand what is 
        happening one really needs to look at the raw data, frame indices, valid
        frames (no shutter), etc...  This will be need to be documented much more
        thoroughly in the future, but for now: Handle with care.
        """

        if self.which_setup=='cool new setup':
            emangles = self.motors.emission_angles
        else:
            emangles = np.array( [self.emission_motor.angle(t, exposuretime=self.camera_data.exposuretime) \
                                      for t in self.timeaxis] )
#        print emangles[:10]

        # frames are valid where emangles is not equal to -1
        validframes = emangles != -1
    
        emangles_rounded_valid = np.round(emangles[validframes], decimals=2)

#        print emangles_rounded_valid.shape

        number_of_lines = np.unique( emangles_rounded_valid ).size
#        print "number_of_lines: %d" % number_of_lines

        # edge 'detection' via diff
        d = np.diff( emangles_rounded_valid )
        d[0] = 1
        d[d!=0] = 1
        d = np.concatenate( (d, np.array([1])) )
        edges    = d.nonzero()[0]
        
        # average gap size between edges
        avewidth = np.mean( np.diff( edges )[:-1] )
        # if the last gap size differs more than ten percent from the average,
        # remove it
        if not avewidth*.9 <= np.diff( edges )[-1] <= avewidth*1.1:
            edges = edges[:-1]

        # integer division to find out how many complete portraits we have
        Nportraits = np.diff(edges).size / number_of_lines 

        indices = np.zeros( (Nportraits,2), dtype=np.int )
        for i in range(Nportraits):
            indices[i,0] = edges[i*number_of_lines]+1
            indices[i,1] = edges[(i+1)*number_of_lines]

        # These indices will discard the first frame, despite it being in principle
        # a valid frame. You can 'repair' that by doing:
        #    indices[0,0] = 0
        # However, we think that the first frame could be affected by the shutter, and
        # the overall behaviour of the code is a bit more consistent this way.
        if self.which_setup=='cool new setup':
            indices[0,0] = 0

        #print indices

        if self.datamode=="truedata":
            # look up indices into all (not just valid) frames
            indices = validframes.nonzero()[0][indices]
        elif self.datamode=="validdata":
            pass
        else:
            raise ValueError("You screwed up defining the datamode: %s" % (self.datamode))

        self.portrait_indices = indices

#        return emangles, emangles_rounded_valid, d


    def assign_portrait_data( self ):  #startstop, data, mode ):
        """Generates portrait list _for each spot_. 
        Each list element is a full portrait. 
        We basically split the output of collect_data(), using the indices
        provided by startstop(), and the spot index.
        The output is independent of _mode_, it only contains valid data.
        """
        pind = self.portrait_indices
        Nportraits = pind.shape[0]

        for si,spot in enumerate(self.spots):
            # create empty list
            portraitlist = []
            # go through all portraits
            for n in range(Nportraits):
                # grab nth portrait
                d = self.data[pind[n,0]:pind[n,1]+1, :]
                if self.datamode=='truedata':
                    # use only valid rows
                    d = d[d[:,1]==1]
                    # from the remaining (valid) rows, grab
                    # columns ex, em and Int
                    ex = d[:, 2]
                    em = d[:, 3]
                    I  = d[:, 4+si]
                elif self.datamode=='validdata':            
                    # simply grab columns ex, em and Int
                    ex = d[:, 1]
                    em = d[:, 2]
                    I  = d[:, 3+si]
                # store portrait object in list
                portraitlist.append( Portrait( ex, em, I, spot ) )

            # store list in spot object
            spot.portraits = portraitlist
        

    def write_data( filename, header=False ):
        """Helper-function which takes the output of collect_data() and
        writes it (possibly with header) into a file.
        """
        fhandle = open( filename, 'wt' )
        if self.datamode=='truedata':
            if header:
                fhandle.write("FrameNumber\t Validity\t excitation\t emission\t Intensities....\n")
            np.savetxt( fhandle, self.data, '%f\t' )
        elif self.datamode=='validdata':
            if header:
                fhandle.write("FrameNumber\t excitation\t emission\t Intensities....\n")
            np.savetxt( fhandle, self.data, '%f\t' )
        else:
            fhandle.close()
            raise hell

        fhandle.close()


    def fit_all_portraits( self, evaluate_portrait_matrices=True ):
        # we assume that the number of portraits and lines is the same 
        # for all spots (can't think of a reason why that shouldn't be the case).
        Nportraits = self.portrait_indices.shape[0]
        Nlines     = len( self.spots[0].portraits[0].lines )

        # for each portrait ---- outermost loop, we do portraits in series
        for pi in range(Nportraits):
            # averageportrait = np.zeros_like( portraitlist[0].matrix )
            # for p in spot.portraits:
            #     averageportrait += p.matrix
            # averageportrait /= len(spot.portraits)

            # spot.averageportrait = averageportrait

            # part I, 'horizontal fitting' of the lines of constant emission angles

            # for each line ---- we do lines in series, __but all spots in parallel__:
            for li in range(Nlines):

                # get excitation angle array (same for all spots!)
                exangles    = self.spots[0].portraits[pi].lines[li].exangles

                # create list of intensity arrays (one array for each spot)
                intensities = [spot.portraits[pi].lines[li].intensities for spot in self.spots]
                # turn into numpy array and transpose
                intensities = np.array( intensities ).T

                phase, I0, M, resi = self.cos_fitter( exangles, intensities ) 

                # write cosine parameters into line object
                for si in range(len(self.spots)):
                    self.spots[si].portraits[pi].lines[li].set_fit_params( phase[si], I0[si], M[si], resi[si] )

            # part II, 'vertical fitting' --- we do each spot by itself, but 
            # fit all verticals in parallel

            for si in range(len(self.spots)):
                print "spot fit done (%d/%d)" % (si,pi)
                # collect list of unique emission angles
                emangles = [l.emangle for l in self.spots[si].portraits[pi].lines]
                # turn into array, transpose and squeeze
                emangles = np.squeeze(np.array( emangles ).T)
                
                # evaluate cosine-fit at these em_angles, on a grid of ex_angles:
                fitintensities = [ l.cosValue( self.excitation_angles_grid ) \
                                     for l in self.spots[si].portraits[pi].lines ]
                fitintensities = np.array( fitintensities )

                phase, I0, M, resi = self.cos_fitter( emangles, fitintensities )
                
                # store vertical fit params
                self.spots[si].portraits[pi].vertical_fit_params = [phase, I0, M, resi]

                if evaluate_portrait_matrices:
                    # evaluate portrait matrix
                    mycos = lambda a, ph, I, M: I*( 1+M*( np.cos(2*(a-ph)) ) )
                    pic = np.zeros( (self.emission_angles_grid.size, self.excitation_angles_grid.size) )
                    for exi in range( self.excitation_angles_grid.size ):
                        pic[:,exi] = mycos( self.emission_angles_grid, phase[exi], I0[exi], M[exi] )

                    self.spots[si].portraits[pi].matrix = pic

        if evaluate_portrait_matrices:
            for s in self.spots:
                averagematrix = np.zeros_like( s.portraits[0].matrix )
                for p in s.portraits:
                    averagematrix += p.matrix

                averagematrix /= len(s.portraits)

                s.averagematrix = averagematrix


    def fit_all_lines_spot_parallel( self ):
        # init average portrait matrices, so that we can write to them without
        # having to store a matrix for each portrait
        for s in self.validspots:
            s.averagematrix = np.zeros( (self.emission_angles_grid.size, self.excitation_angles_grid.size) )

        # we assume that the number of portraits and lines is the same 
        # for all spots (can't think of a reason why that shouldn't be the case).
        Nportraits = self.portrait_indices.shape[0]
        Nlines     = len( self.validspots[0].portraits[0].lines )

        # for each portrait ---- outermost loop, we do portraits in series
        for pi in range(Nportraits):
            # averageportrait = np.zeros_like( portraitlist[0].matrix )
            # for p in spot.portraits:
            #     averageportrait += p.matrix
            # averageportrait /= len(spot.portraits)

            # spot.averageportrait = averageportrait

            # part I, 'horizontal fitting' of the lines of constant emission angles

            # for each line ---- we do lines in series, __but all spots in parallel__:
            for li in range(Nlines):

                # get excitation angle array (same for all spots!)
                exangles    = self.validspots[0].portraits[pi].lines[li].exangles

                # create list of intensity arrays (one array for each spot)
                intensities = [spot.portraits[pi].lines[li].intensities for spot in self.validspots]

                # turn into numpy array and transpose
                intensities = np.array( intensities ).T

                exa = exangles.copy()
                phase, I0, M, resi, fit, rawfitpars, mm = self.cos_fitter( exa, intensities, \
                                                                               self.Nphases_for_cos_fitter ) 

                # write cosine parameters into line object
                for si in range(len(self.validspots)):
                    self.validspots[si].portraits[pi].lines[li].set_fit_params( phase[si], I0[si], M[si], resi[si] )


    def compute_modulation_in_emission( self,portrait ):
        # part II, 'vertical fitting' --- we do each spot by itself, but 
        # fit all verticals in parallel

        # collect list of unique emission angles (same for all spots!)                    
        emangles = [l.emangle for l in portrait.lines]
        # turn into array, transpose and squeeze
        emangles = np.squeeze(np.array( emangles ).T)

        # evaluate cosine-fit at these em_angles, on a grid of ex_angles:
        fitintensities = np.array([l.cosValue( self.excitation_angles_grid ) for l in portrait.lines])

        phase, I0, M, resi, fit, rawfitpars, mm = self.cos_fitter( emangles, fitintensities, \
                                                                       self.Nphases_for_cos_fitter ) 
        
        # phasor addition!
        proj_em = np.real( rawfitpars[0,:] * np.exp( 1j*rawfitpars[1,:] ) \
                               * np.exp( 1j*self.emission_angles_grid ) )

        phase, I0, M, resi, fit, rawfitpars, mm = self.cos_fitter( self.emission_angles_grid, proj_em, \
                                                                       self.Nphases_for_cos_fitter ) 
        portrait.phase_em = phase[0]
        portrait.M_em = M
        

                
#             # evaluate portrait matrix
#                     mycos = lambda a, ph, I, M: I*(1+M*(np.cos(2*(a-ph)*np.pi/180.0)))
#                     pic = np.zeros( (self.emission_angles_grid.size, self.excitation_angles_grid.size) )
#                     for exi in range( self.excitation_angles_grid.size ):
#                         pic[:,exi] = mycos( self.emission_angles_grid, phase[si][exi], I0[si][exi], M[si][exi] )
#                     s.averagematrix += pic
# #                    s.portraits[pi].matrix = pic

#         for s in self.spots:
#             s.averagematrix /= Nportraits



    def fit_all_portraits_spot_parallel( self ):   #, evaluate_portrait_matrices=True ):

        # init average portrait matrices, so that we can write to them without
        # having to store a matrix for each portrait
        for s in self.validspots:
#            s.averagematrix = np.zeros( (self.emission_angles_grid.size, self.excitation_angles_grid.size) )
            s.residual = 0

        # we assume that the number of portraits and lines is the same 
        # for all spots (can't think of a reason why that shouldn't be the case).
        Nportraits = self.portrait_indices.shape[0]
        Nlines     = len( self.validspots[0].portraits[0].lines )

        # for each portrait ---- outermost loop, we do portraits in series
        for pi in range(Nportraits):
            # averageportrait = np.zeros_like( portraitlist[0].matrix )
            # for p in spot.portraits:
            #     averageportrait += p.matrix
            # averageportrait /= len(spot.portraits)

            # spot.averageportrait = averageportrait

            # part I, 'horizontal fitting' of the lines of constant emission angles

            # for each line ---- we do lines in series, __but all spots in parallel__:
            for li in range(Nlines):

                # get excitation angle array (same for all spots!)
                exangles    = self.validspots[0].portraits[pi].lines[li].exangles

                # create list of intensity arrays (one array for each spot)
                intensities = [spot.portraits[pi].lines[li].intensities for spot in self.validspots]

                # turn into numpy array and transpose
                intensities = np.array( intensities ).T

                exa = exangles.copy()

                # import matplotlib.pyplot as plt
                # plt.figure()
                # plt.plot(exa, intensities, 'o:')

#                print "line"
                phase, I0, M, resi, fit, rawfitpars, mm = self.cos_fitter( exa, intensities, \
                                                                               self.Nphases_for_cos_fitter ) 

                # for jj in range(len(phase)):
                #     plt.plot( exa, I0[jj]*(1+M[jj]*np.cos(2*np.pi/180.0*(exa-phase[jj]))) )
                # raise hell

                # write cosine parameters into line object
                for si in range(len(self.validspots)):
                    self.validspots[si].portraits[pi].lines[li].set_fit_params( phase[si], I0[si], M[si], resi[si] )


            # gather residuals for this protrait
            for si in range(len(self.validspots)):
                self.validspots[si].residual = np.sum( [ l.resi for l in self.validspots[si].portraits[pi].lines ] )


            # part II, 'vertical fitting' --- we do each spot by itself, but 
            # fit all verticals in parallel

            # collect list of unique emission angles (same for all spots!)                    
            emangles = [l.emangle for l in self.validspots[0].portraits[pi].lines]
            # turn into array, transpose and squeeze
            emangles = np.squeeze(np.array( emangles ).T)

            # evaluate cosine-fit at these em_angles, on a grid of ex_angles:
            fitintensities = [ np.array( [l.cosValue( self.excitation_angles_grid ) \
                                             for l in s.portraits[pi].lines]) for s in self.validspots ]
#            print 'l=',len(fitintensities)
#            print 's=',fitintensities[0].shape
            fitintensities = np.hstack( fitintensities )
#            print fitintensities.shape

            # print "vertical, portrait %d" % (pi)
            # print fitintensities.shape

            phase, I0, M, resi, fit, rawfitpars, mm = self.cos_fitter( emangles, fitintensities, \
                                                                           self.Nphases_for_cos_fitter ) 
                
            # store vertical fit params
            phase = np.hsplit(phase, len(self.validspots))
            I0    = np.hsplit(I0, len(self.validspots))
            M     = np.hsplit(M, len(self.validspots))
            resi  = np.hsplit(resi, len(self.validspots))
            mm    = np.hsplit(mm, len(self.validspots))
            for si,s in enumerate(self.validspots):
                s.portraits[pi].vertical_fit_params = [ phase[si], I0[si], M[si], resi[si], mm[si] ]

#                 if evaluate_portrait_matrices:
#                     # evaluate portrait matrix
#                     mycos = lambda a, ph, I, M: I*( 1+M*( np.cos(2*(a-ph)) ) )
#                     pic = np.zeros( (self.emission_angles_grid.size, self.excitation_angles_grid.size) )
#                     for exi in range( self.excitation_angles_grid.size ):
#                         pic[:,exi] = mycos( self.emission_angles_grid, phase[si][exi], I0[si][exi], M[si][exi] )
#                     s.averagematrix += pic
# #                    s.portraits[pi].matrix = pic

#         for s in self.validspots:
#             s.averagematrix /= Nportraits
#             s.residual /= Nportraits



        # if evaluate_portrait_matrices:
        #     for s in self.spots:
        #         averagematrix = np.zeros_like( s.portraits[0].matrix )
        #         for p in s.portraits:
        #             averagematrix += p.matrix

        #         averagematrix /= len(s.portraits)

        #         s.averagematrix = averagematrix



    # def perform_fit( self ):
    #     mycos = lambda a, ph, I, M: I*(1+M*(np.cos(2*(a-ph)*np.pi/180.0)))

    #     # fit each line with a cos**2
    #     for l in self.lines:
    #         # fit line
    #         phase, I0, M, resi = CosineFitter( l.exangles, l.intensities ) 
    #         # store results
    #         l.cosParams( phase, I0, M, resi )

    #     # now create grid for excitation angles
    #     exangs = self.excitation_angles_grid

    #     # and get 'data' from the fits of the lines

    #     ### FIXMEFIXMEFIXME:  - here we only support single spots at the moment !!!
    #     ###                   - check Lines.cosValue for correct behaviour !!!
    #     ###                   - data should have shape [Nemangles, Nexangles, Nspots] !!!
        
    #     data   = np.zeros( (len(self.lines), exangs.size+1) )
    #     for i,l in enumerate(self.lines):
    #         data[i,:] = np.hstack( (l.emangle, l.cosValue(exangs)) )
    #     # then fit all those lines in one go, because the em-angles
    #     # at which data is defined, are the same for all 
    #     phases, I0s, M0s, resis = CosineFitter( data[:,0], data[:,1:] ) 
    #     self.phases = phases
    #     self.I0s    = I0s
    #     self.M0s    = M0s
    #     self.resis  = resis

    #     emangs = self.emission_angles_grid
    #     # take a picture:
    #     # we set this up such that each column corresponds to one excitation angle 
    #     # and each row corresponds to one emission angle
    #     picture = np.zeros( (emangs.size, exangs.size) )
    #     for i in range(picture.shape[1]):
    #         picture[:,i] = mycos( emangs, phases[i], I0s[i], M0s[i] )

    #     self.picture = picture



    def find_modulation_depths_and_phases( self ):

        # test = np.outer( 2*(1+.5*np.cos(2*self.emission_angles_grid*np.pi/180.0+.4)), \
        #                      3*(1+.2*np.cos(2*self.excitation_angles_grid*np.pi/180.0+1)).reshape((\
        #             self.excitation_angles_grid.size,1)) )

        # proj_ex = np.array( [np.mean( test, axis=0 ) for s in self.spots] ).T
        # proj_em = np.array( [np.mean( test, axis=1 ) for s in self.spots] ).T
        # import matplotlib.pyplot as plt
        # plt.interactive(True)
        # plt.imshow(test)
        # plt.figure()
        # plt.plot( proj_ex )
        # plt.plot( proj_em )

        # projection onto the excitation axis (ie over all emission angles),
        # for all spots, one per column
        proj_ex = []
        proj_em = []
        for s in self.validspots:
            sam = s.recover_average_portrait_matrix()
            s.proj_ex = np.mean( sam, axis=0 )
            s.proj_em = np.mean( sam, axis=1 )
            proj_ex.append( s.proj_ex )
            proj_em.append( s.proj_em )
        proj_ex = np.array(proj_ex).T
        proj_em = np.array(proj_em).T

        # proj_ex = np.array( [np.mean( s.recover_average_portrait_matrix(), axis=0 ) for s in self.validspots] ).T
        # # same for projection onto emission axis
        # proj_em = np.array( [np.mean( s.recover_average_portrait_matrix(), axis=1 ) for s in self.validspots] ).T

        # fitting
        ph_ex, I_ex, M_ex, r_ex, fit_ex, rawfitpars_ex, mm = self.cos_fitter( self.excitation_angles_grid, proj_ex, self.Nphases_for_cos_fitter )
        ph_em, I_em, M_em, r_em, fit_em, rawfitpars_em, mm= self.cos_fitter( self.emission_angles_grid, proj_em, self.Nphases_for_cos_fitter )

        # print ph_ex, I_ex, M_ex, r_ex, fit_ex, rawfitpars_ex
        # print ph_em, I_em, M_em, r_em, fit_em, rawfitpars_em
        # raise hell

        # print 'uosad'
        # print proj_ex.shape
        # print proj_em.shape
        # import matplotlib.pyplot as plt
        # plt.interactive(True)
        # plt.plot( self.excitation_angles_grid, proj_ex, 'b-' )
        # plt.plot( self.emission_angles_grid, proj_em, 'r-' )
        # plt.draw()
        # import time
        # time.sleep(1)

        # assignment
        LS = ph_ex - ph_em
        LS[LS >  np.pi/2] -= np.pi
        LS[LS < -np.pi/2] += np.pi
        for si,s in enumerate(self.validspots):
            s.phase_ex = ph_ex[si]
            s.M_ex     = M_ex[si]
            s.phase_em = ph_em[si]
            s.M_em     = M_em[si]
            s.LS       = LS[si]
            # store in coverage maps
            self.M_ex_image[ s.coords[1]:s.coords[3]+1, s.coords[0]:s.coords[2]+1 ] = s.M_ex
            self.M_em_image[ s.coords[1]:s.coords[3]+1, s.coords[0]:s.coords[2]+1 ] = s.M_em
            self.phase_ex_image[ s.coords[1]:s.coords[3]+1, s.coords[0]:s.coords[2]+1 ] = s.phase_ex
            self.phase_em_image[ s.coords[1]:s.coords[3]+1, s.coords[0]:s.coords[2]+1 ] = s.phase_em
            self.LS_image[ s.coords[1]:s.coords[3]+1, s.coords[0]:s.coords[2]+1 ] = s.LS        


        # for spot in self.spots:
        #     ap = spot.averagematrix

        #     # excitation
        #     a = self.excitation_angles_grid
        #     d = np.mean(ap, axis=0)
        #     assert a.size==d.size
        #     ph, I, M, r   = CosineFitter( a, d ) 
        #     spot.phase_ex = ph[0]
        #     spot.M_ex     = M[0]

        #     # emission
        #     a = self.emission_angles_grid
        #     d = np.mean(ap, axis=1)
        #     assert a.size==d.size
        #     ph, I, M, r   = CosineFitter( a, d ) 
        #     spot.phase_em = ph[0]
        #     spot.M_em     = M[0]
       
        #     # luminescence shift
        #     LS = spot.phase_ex - spot.phase_em
        #     if LS>90:
        #         LS -= 180
        #     elif LS<-90:
        #         LS += 180
        #     spot.LS = LS


    def ETrulerFFT( self, slope=7, newdatalength=2048 ):
        # we re-sample the 2D portrait matrix along a slanted line to
        # get a 1D array which contains information about both angular
        # dimensions

        # first we compute the indices into the 2D portrait matrix,
        # this depends only on the angular grids and is therefore the same for
        # all spots and portraits.
        
        # along one direction we increase in single steps along the angular grid:
        ind_em = 1*      np.linspace(0,newdatalength-1,newdatalength).astype(np.int)
        # along the other we have a slope
        ind_ex = slope * np.linspace(0,newdatalength-1,newdatalength).astype(np.int)

        # both index arrays need to wrap around their angular axes
        ind_em = np.mod( ind_em, self.emission_angles_grid.size-1 )
        ind_ex = np.mod( ind_ex, self.excitation_angles_grid.size-1 )
        
        # Now we use these to get the new data.
        # We could do this for every portrait of every spot, but we'll 
        # restrict ourselves to the average portrait of each spot.

        # the angular grids likely include redundancy at the edges, and
        # we need to exclude those to not oversample
        newdata = []
        for s in self.validspots:
            sam = s.recover_average_portrait_matrix()
            if self.excitation_angles_grid[-1]==np.pi:
                sam = sam[:,:-1]
            if self.emission_angles_grid[-1]==np.pi:
                sam = sam[:-1,:]
            newdata.append( sam[ ind_em,ind_ex ] )
#            s.pruned_averagematrix = sam
#       newdata = np.array( [ s.pruned_averagematrix[ind_em, ind_ex] for s in self.validspots ] )
        newdata = np.array( newdata )

#        self.newexangles = self.excitation_angles_grid[ ind_ex ]
#        self.newemangles = self.emission_angles_grid[ ind_em ]

        # voila, we have new 1d data

        # now we work out the position of the peaks in the FFTs of these new data columns

        f = np.fft.fft( newdata, axis=1 )
        powerspectra = np.real( f*f.conj() )/newdatalength
#        print powerspectra.shape
        normpowerspectra = powerspectra[:,1:newdatalength/2] \
            /np.outer( np.sum(powerspectra[:,1:newdatalength/2],axis=1), np.ones( (1,newdatalength/2-1) ) )

        # first peak index, pops out at newdatalength / grid  (we are awesome.)
        i1 = newdatalength/(self.excitation_angles_grid.size-1.0)
        # second
        i2 = i1*(slope-1)
        i3 = i1*slope
        i4 = i1*(slope+1)
        df = i1/3
        
        # import matplotlib.pyplot as plt
        # plt.plot( np.arange(normpowerspectra.shape[1]), \
        #               normpowerspectra.T, 'b' )
        # plt.plot( np.arange(normpowerspectra.shape[1])[np.round(i1-df):np.round(i1+df)], \
        #               normpowerspectra.T[np.round(i1-df):np.round(i1+df),:], 'r' )
        # plt.plot( np.arange(normpowerspectra.shape[1])[np.round(i2-df):np.round(i2+df)], \
        #               normpowerspectra.T[np.round(i2-df):np.round(i2+df),:], 'g' )
        # plt.plot( np.arange(normpowerspectra.shape[1])[np.round(i3-df):np.round(i3+df)], \
        #               normpowerspectra.T[np.round(i3-df):np.round(i3+df),:], 'y' )
        # plt.plot( np.arange(normpowerspectra.shape[1])[np.round(i4-df):np.round(i4+df)], \
        #               normpowerspectra.T[np.round(i4-df):np.round(i4+df),:], 'm' )
        # plt.draw()
        # raise hell

        self.peaks = np.array( [ np.sum(normpowerspectra[:, np.round(ii-df):np.round(ii+df)], axis=1) \
                      for ii in [i1,i2,i3,i4] ] )

        # now go over all spots
        cet=0
        for si,s in enumerate(self.validspots):

#            import sys
#            sys.stdout.flush()

            # if we deviate from the normalized sum by more than 5%,
            # we shouldn't use this ruler
            if np.abs(np.sum( self.peaks[:,si] )-1) > .08:
                print 'fuck. Data peaks are weird... %f' % (np.sum(self.peaks[:,si]))
                self.validspots[si].ET_ruler = np.nan
            
            # now let's rule
            crossdiff = self.peaks[1,si]-self.peaks[3,si]
            
            # 3-dipole model (all of same length, no ET) starts here
            kappa     = .5 * np.arccos( .5*(3*self.validspots[si].M_ex-1) ) 
            alpha     = np.array([ -kappa, 0, kappa ])
            
            phix =   np.linspace(0,newdatalength-1,newdatalength)*2*np.pi/180
            phim = 7*np.linspace(0,newdatalength-1,newdatalength)*2*np.pi/180

            ModelNoET = np.zeros_like( phix )
            for n in range(3):
                ModelNoET[:] += np.cos(phix-alpha[n])**2 * np.cos(phim-alpha[n])**2
            ModelNoET /= 3
            MYY = np.fft.fft(ModelNoET)
            MYpower = np.real( (MYY*MYY.conj()) )/MYY.size

            # import matplotlib.pyplot as plt
            # plt.plot( np.arange(MYpower.size), MYpower, 'b' )
            # raise hell
            
            MYpeaks = np.array( [ np.sum( MYpower[np.round(ii-df):np.round(ii+df)] ) \
                                      for ii in [i1,i2,i3,i4] ] )
            MYpeaks /= np.sum(MYpeaks)
            
            # test again if peaks make sense
            if np.abs(np.sum( MYpeaks )-1) > .08:
                print 'fuck. MYpeaks is off... %f' % (np.sum( MYpeaks ))
                self.validspots[si].ET_ruler = np.nan

            MYcrossdiff = MYpeaks[1]-MYpeaks[3]
            # model done
            
            ruler = 1-(crossdiff/MYcrossdiff)

            if (ruler < -.1) or (ruler > 1.1):
                print "Shit, ruler has gone bonkers (ruler=%f). Spot #%d" % (ruler,si)
                print "Will continue anyways and set ruler to zero or one (whichever is closer)."
                print "You can thank me later."
                cet+=1
                print cet

            if ruler < 0:
                ruler = 0
            if ruler > 1:
                ruler = 1

            self.validspots[si].ET_ruler = ruler
            self.ET_ruler_image[ self.validspots[si].coords[1]:self.validspots[si].coords[3]+1, \
                               self.validspots[si].coords[0]:self.validspots[si].coords[2]+1 ] = ruler
        #print i1,i2,i3,i4,df


    def ETmodel( self, fac=1e4, pg=1e-9, epsi=1e-11 ):

        from fitting import fit_portrait_single_funnel_symmetric

        for si,s in enumerate(self.validspots):
            print 'ETmodel fitting spot %d' % si

            # we 'correct' the modulation in excitation to be within 
            # limits of reason (and proper arccos functionality)
            mex = np.clip( s.M_ex, .000001, .999999 )

            a0 = [mex, 0, 1]
            EX, EM = np.meshgrid( self.excitation_angles_grid, self.emission_angles_grid )
            funargs = (EX, EM, s.averagematrix, mex, s.phase_ex, 'fitting')

            LB = [0.001,   -np.pi/2, 0]
            UB = [0.999999, np.pi/2, 2*(1+mex)/(1-mex)*.999]
            print "upper limit: ", 2*(1+s.M_ex)/(1-s.M_ex)
            print "upper limit (fixed): ", 2*(1+mex)/(1-mex)

            a = so.fmin_l_bfgs_b( func=fit_portrait_single_funnel_symmetric, \
                                      x0=a0, \
                                      fprime=None, \
                                      args=funargs, \
                                      approx_grad=True, \
                                      epsilon=epsi, \
                                      bounds=zip(LB,UB), \
                                      factr=fac, \
                                      pgtol=pg )

            et,A = fit_portrait_single_funnel_symmetric( a[0], EX, EM, s.averagematrix, mex, s.phase_ex, \
                                                             mode='show_et_and_A', use_least_sq=True)
            s.ETmodel_md_fu = a[0][0]
            s.ETmodel_th_fu = a[0][1]
            s.ETmodel_gr    = a[0][2]
            s.ETmodel_et    = et            

            self.ET_model_md_fu_image[ s.coords[1]:s.coords[3]+1, s.coords[0]:s.coords[2]+1 ] = a[0][0]
            self.ET_model_th_fu_image[ s.coords[1]:s.coords[3]+1, s.coords[0]:s.coords[2]+1 ] = a[0][1]
            self.ET_model_gr_image[ s.coords[1]:s.coords[3]+1, s.coords[0]:s.coords[2]+1 ] = a[0][2]
            self.ET_model_et_image[ s.coords[1]:s.coords[3]+1, s.coords[0]:s.coords[2]+1 ] = et

            print 'fit done\t',a[0],
            print ' et=',et,
            print ' A=',A

            # et, bla = fit_portrait_single_funnel_symmetric( a[0], EX, EM, \
            #                                                     s.averagematrix, \
            #                                                     mex, s.phase_ex, mode='display' )


    def ETmodel_de( self, fac=1e2, pg=1e-10, epsi=1e-12 ):

        from fitting import fit_portrait_single_funnel_symmetric, wrapper_for_de

        import sys
        sys.path.insert(1,'/home/kiwimatto/Desktop/python_libs')
        import diffevol
        

        for si,s in enumerate(self.validspots):
            print 'ETmodel fitting spot %d' % si
            mex = np.clip( s.M_ex, .000001, .999999 )
            a0 = [mex, .5, 0, 1]
            EX, EM = np.meshgrid( self.excitation_angles_grid, self.emission_angles_grid )
            funargs = (EX, EM, s.averagematrix, mex, s.phase_ex, 'fitting', False)

            LB = [0.001, -np.pi/2, 0, 0]
            UB = [0.999,  np.pi/2, 2*(1+mex)/(1-mex)*.999, 1]

            ds = diffevol.scenario( scorefunction=wrapper_for_de, \
                                        parameter_limits=np.array( zip(LB,UB) ), \
                                        Npop=40, \
                                        goal='min', \
                                        extras=funargs )

            a = ds.run_until( )

            print 'fit done\t',a
            s.ETmodel_md_fu = a[0]
            s.ETmodel_th_fu = a[1]
            s.ETmodel_gr    = a[2]
            s.ETmodel_et    = a[3]


        #     et, bla = fit_portrait_single_funnel_symmetric( a[0], EX, EM, \
        #                                                         s.averagematrix/np.sum(s.averagematrix), \
        #                                                         s.M_ex, s.phase_ex, mode='display' )
        # return bla

        # fit_portrait_single_funnel_symmetric( params, ex_angles, em_angles, Ftot, \
        #                                           mod_depth_excitation, phase_excitation, mode )



    def chew( self, quiet=False, loud=False ):
        print "collecting data..."
        self.collect_data()
        print "startstop..."
        self.startstop()
        print "assigning portrait data..."
        self.assign_portrait_data()        
        self.are_spots_valid()

        # for s in self.validspots:       
        #     print s.intensity
        #     s.intensity = None
#        self.data = None             # this doesn't seem to do anything memory-wise
                                     # (are these all just pointers??)
#        self.camera_data = None      # this helps (as expected)

        print "fitting all portraits"
#        self.fit_all_portraits()

        import time as stopwatch
        self.fit_all_portraits_spot_parallel()

        print "finding mod depths and phases..."
        self.find_modulation_depths_and_phases()
        print "ETruler..."
        self.ETrulerFFT()
        print "ETmodel..."

        tstart = stopwatch.time()
        self.ETmodel()
        print "time taken: %fs" % (stopwatch.time()-tstart)

        if not quiet:
            print "Quick report:"
            print "-------------"
            print "Number of frames: %d"  % (self.timeaxis.size)
            print "Number of valid frames: %d" % (self.Nvalidframes)
            print "Number of spots: %d" % (len(self.validspots))
            print "Number of portraits: %d" % (len(self.validspots[0].portraits))
            for i,p in enumerate( self.validspots[0].portraits ):
                print "Portrait #%d (%d frames)" % (i,p.exangles.size)
        if loud:
            for si,spot in enumerate( self.validspots ):
                print "Spot #%d:" % (si)
                print "\tModulation depth in excitation: %f" % (spot.M_ex)
                print "\tPhase in excitation: %f" % (spot.phase_ex)
                print "\tModulation depth in emission:   %f" % (spot.M_em)
                print "\tPhase in emission  : %f" % (spot.phase_em)
                print "\tLS: %f" % (spot.LS)

    # def show_average_matrix( self ):
    #     plt.matshow( self.averageportrait, origin='bottom')
    #     plt.plot( [0,180], [0,180], 'k-' )
    #     plt.xlim( 0, 180 )
    #     plt.ylim( 0, 180 )      


    def chew_a_bit( self, SNR=30, quiet=False, loud=False ):
        self.collect_data()
        self.startstop()
        self.assign_portrait_data()        
        self.are_spots_valid( SNR )
        self.fit_all_portraits_spot_parallel()
        self.find_modulation_depths_and_phases()

#        self.ETrulerFFT()

#        for s in self.validspots:
#            print s
#            print "M_ex=%3.2f\tM_em=%3.2f\tphase_ex=%3.2fdeg\tphase_em=%3.2fdeg\tLS=%3.2fdeg" % \
#                ( s.M_ex,s.M_em, s.phase_ex*180/np.pi, s.phase_em*180/np.pi, s.LS*180/np.pi )

    def chew_AM( self, quiet=False, loud=False, SNR=10 ):
        self.collect_data()
        self.startstop()
        self.assign_portrait_data()        
        self.are_spots_valid( SNR=SNR )
        if len(self.validspots)<1:
            raise ValueError("No valid spots found! Reduce SNR demands or re-measure...")

        self.fit_all_portraits_spot_parallel()
        self.find_modulation_depths_and_phases()

        for s in self.validspots:
#            print s
            print "M_ex=%3.2f\tM_em=%3.2f\tphase_ex=%3.2fdeg\tphase_em=%3.2fdeg\tLS=%3.2fdeg" % \
                ( s.M_ex,s.M_em, s.phase_ex*180/np.pi, s.phase_em*180/np.pi, s.LS*180/np.pi )


    def are_spots_valid(self, SNR=10, quiet=False):
        # do we actually have the background std
        bgstd = 0
        if hasattr( self, 'bg_spot' ):
            bgstd = self.bg_spot.std
        else:
            print "Dude --- no background spot defined, therefore no standard deviation. Will treat all spots as valid (i.e. as having sufficient intensity)."

        # then we create a new list containing valid spots only
        validspots = []   
        validspotindices = []
        for si,s in enumerate(self.spots):
            s.SNR = s.mean_intensity/bgstd
            if s.SNR > SNR:
                validspots.append(s)
                validspotindices.append(si)
            # store SNR in SNR_image
            s.store_property_in_image( self.SNR_image, 'SNR' )    # let's see if this works...


        # and store in movie object
        self.validspots = validspots
        self.validspotindices = validspotindices        

        if not quiet: print "Got %d valid spots" % len(self.validspots)

                

class CameraData:
    def __init__( self, spe_filename, compute_frame_average=False, in_counts_per_sec=True ):
        # load SPE  ---- this will work for SPE format version 2.5 (probably not for 3...)

        self.filename           = spe_filename

        if self.filename.split('.')[-1]=='npy':   # we got test data, presumably
            print "======== TEST DATA IT SEEMS =========="
            self.rawdata      = np.load(self.filename)
            self.datasize     = self.rawdata.shape
            self.exposuretime = .1    # in seconds

        else:                                     # we got real data 
            self.rawdata_fileobject = MyPrincetonSPEFile( self.filename )
            self.rawdata            = self.rawdata_fileobject.return_Array()#.astype(np.float64)
            self.datasize           = self.rawdata_fileobject.getSize()
            self.exposuretime       = self.rawdata_fileobject.Exposure   # in seconds
            # scale signal to counts/second:
            if in_counts_per_sec:
                self.rawdata           /= self.rawdata_fileobject.Exposure
            self.rawdata_fileobject.close_file()
            del(self.rawdata_fileobject)
        if compute_frame_average:
            self.average_image      = np.mean( self.rawdata, axis=0 )

        ###  extract or generate time stamps ###
        #  here we do not have timestamps for each frame, so we
        #  generate time axis from SPE exposure data and number of frames
        self.timestamps = np.linspace( 0, self.exposuretime*self.rawdata.shape[0], \
                                           self.rawdata.shape[0], endpoint=False )


class Spot:
    def __init__(self, rawdata, coords, bg, int_type, label, parent, is_bg_spot=False, \
                     blankdata=False):
        """
        There's something noteworthy (speak: important) about the coordinates
        which define the box that is the 'spot'. First of all, the convention
        is [left, bottom, right, top], where the coordinates (0,0) define the
        _lower left corner_ of the image. If you plot an image with matplotlib's 
        imshow() or matshow(), then the origin is in the _top left_ (the way 
        you would write a matrix on paper) --- so there's potential for confusion
        here. Secondly, the coordinates given are interpreted as inclusive 
        boundaries, so that [3,3,5,5] gives a 3x3 spot from which intensities 
        are computed. This explains the occurence of various +1s in the code 
        below...
        """

        self.coords = coords    #[left, bottom, right, top]
        self.label  = label
        self.width  = coords[2] -coords[0] +1
        self.height = coords[3] -coords[1] +1
        self.parent = parent

        # work out frame-dependent intensities for that spot
        # - mean:
        if int_type=='mean':
            I  = np.sum( np.sum( \
                    rawdata[:, coords[1]:coords[3]+1, coords[0]:coords[2]+1 ], \
                        axis=2), axis=1 ).astype( np.float )
            I /= self.width*self.height
            # work out blank signal if present
            if blankdata:
                Iblank  = np.sum( self.blank_image[ coords[1]:coords[3]+1, coords[0]:coords[2]+1 ] )
                Iblank /= self.width*self.height

        elif int_type=='max':
            # - maximum:
            I = np.max( np.max( \
                    rawdata[:, coords[1]:coords[3]+1, coords[0]:coords[2]+1 ], \
                        axis=2), axis=1 ).astype( np.float )
            # work out blank signal if present
            if blankdata:
                Iblank  = np.max( self.blank_image[ coords[1]:coords[3]+1, coords[0]:coords[2]+1 ] )
                Iblank /= self.width*self.height

        elif int_type=='min':
            # - minimum:
            I = np.min( np.min( \
                    self.camera_data.rawdata[:, coords[1]:coords[3]+1, coords[0]:coords[2]+1 ], \
                        axis=2), axis=1 ).astype( np.float )
            # work out blank signal if present
            if blankdata:
                Iblank  = np.min( self.blank_image[ coords[1]:coords[3]+1, coords[0]:coords[2]+1 ] )
                Iblank /= self.width*self.height

        else:
            raise ValueError("Spot __init__ did not understand int_type='%s' (should be mean|max|min)" % (int_type))

        # special: take standard deviation if this is the background spot
        if is_bg_spot:
            self.std  = np.std( rawdata[:, coords[1]:coords[3]+1, coords[0]:coords[2]+1 ] )

        # remove background
        I -= bg
        # remove blank
        if blankdata:
            I -= Iblank

        self.intensity_type = int_type
        self.intensity      = I
        self.mean_intensity = np.mean(I)
        self.bg_correction  = bg
        if not is_bg_spot:
            self.parent.mean_intensity_image[ \
                self.coords[1]:self.coords[3]+1, self.coords[0]:self.coords[2]+1 \
                    ] = self.mean_intensity


    def __str__(self):
        return "Spot object: int_type=%s\tlowerleft=[%d,%d]\twidth=%d\theight=%d\tlabel=%s" % \
            (self.intensity_type, self.coords[0], self.coords[1], \
                 self.coords[2]-self.coords[0]+1, self.coords[3]-self.coords[1]+1, self.label)

    def store_property_in_image(self, image, prop):
        image[ self.coords[1]:self.coords[3]+1, self.coords[0]:self.coords[2]+1 ] = getattr(self,prop)

    def export_averagematrix(self,filename):
        np.save(filename,self.averagematrix)

    def recover_average_portrait_matrix(self):
        pic = self.portraits[0].recover_portrait_matrix()
        n = 1
        while n < len(self.portraits):
            pic += self.portraits[n].recover_portrait_matrix()
            n += 1
        pic /= n
        return pic


    def collect_and_assign(self):
        # grab angles
        if self.parent.which_setup=='cool new setup':
            exangles = self.parent.motors.excitation_angles
            emangles = self.parent.motors.emission_angles
        else:
            exptime = self.parent.camera_data.exposuretime
            exangles = np.array( [self.parent.excitation_motor.angle(t,exposuretime=exptime) \
                                      for t in self.parent.timeaxis] )
            emangles = np.array( [self.parent.emission_motor.angle(t,exposuretime=exptime) \
                                      for t in self.parent.timeaxis] )
        # truth value array for frame validity
        validframes = emangles != -1
        self.parent.Nvalidframes = np.sum(validframes)

        # pick angles of valid frames and round them
        emangles = np.round(emangles[validframes], decimals=2)
        exangles = np.round(exangles[validframes], decimals=2)

        # indices of valid frames
        trueindices = validframes.nonzero()[0]

        # store valid angles and frames temporarily
        ex = []
        em = []
        I  = []
#        for i in range( self.timeaxis[validframes].size ):
        for i in range( np.sum(validframes) ):
            ex.append( exangles[i] )
            em.append( emangles[i] )
            I.append( self.intensity[trueindices[i]] )
        ex = np.array(ex)
        em = np.array(em)
        I  = np.array(I)
                
        # grab portrait indices (generated by Movie.startstop())
        pind = self.parent.portrait_indices
        Nportraits = pind.shape[0]

        # make a list of portraits, using stored angles and frames
        portraitlist = []
        for n in range(Nportraits):
            portraitlist.append( Portrait( ex[pind[n,0]:pind[n,1]+1], em[pind[n,0]:pind[n,1]+1], \
                                               I[pind[n,0]:pind[n,1]+1], self ) )
        # store list in spot object
        self.portraits = portraitlist

        # the spot.intensity is no longer needed
        del(self.intensity)

        # we're done here



    def get_portrait_data(self):
        pind = self.parent.portrait_indices
        Nportraits = pind.shape[0]

        # create empty list
        portraitlist = []
        # go through all portraits
        for n in range(Nportraits):
            # grab nth portrait
            d = self.parent.data[pind[n,0]:pind[n,1]+1, :]
            if self.parent.datamode=='truedata':
                # use only valid rows
                d = d[d[:,1]==1]
                # from the remaining (valid) rows, grab
                # columns ex, em and Int
                ex = d[:, 2]
                em = d[:, 3]
                I  = d[:, 4+si]
            elif self.parent.datamode=='validdata':            
                # simply grab columns ex, em and Int
                ex = d[:, 1]
                em = d[:, 2]
                I  = d[:, 3+si]
            # store portrait object in list
            portraitlist.append( Portrait( ex, em, I, spot ) )

        # store list in spot object
        self.portraits = portraitlist


    def check_if_valid(self,SNR):
        # do we actually have the background std
        bgstd = 0
        if hasattr( self.parent, 'bg_spot' ):
            bgstd = self.parent.bg_spot.std
        else:
            print "Dude --- no background spot defined, therefore no standard deviation. Will treat all spots as valid (i.e. as having sufficient intensity)."

        self.SNR = self.mean_intensity/bgstd
        if self.SNR > SNR:
            self.isvalid = True
        else:
            self.isvalid = False

        
    def cos_fit(self):
        self.residual = 0

        # we assume that the number of portraits and lines is the same 
        # for all spots (can't think of a reason why that shouldn't be the case).
        Nportraits = len(self.portraits)
        Nlines     = len(self.portraits[0].lines )

        # for each portrait ---- outermost loop, we do portraits in series
        for pi in range(Nportraits):
            # part I, 'horizontal fitting' of the lines of constant emission angles

            # for each line ---- we do lines in series, __but all spots in parallel__:
            for li in range(Nlines):

                # get excitation angle array (same for all spots!)
                exangles    = self.portraits[pi].lines[li].exangles

                # create list of intensity arrays (one array for each spot)
                intensities = self.portraits[pi].lines[li].intensities

                # turn into numpy array and make sure it's a column
                intensities = np.array( intensities ).reshape((exangles.size,1))

                exa = exangles.copy()

                phase, I0, M, resi, fit, rawfitpars, mm = self.parent.cos_fitter( exa, intensities, \
                                                                               self.parent.Nphases_for_cos_fitter ) 
                # write cosine parameters into line object
                self.portraits[pi].lines[li].set_fit_params( phase, I0, M, resi )
                # and add residual
                self.residual += resi


            # part II, 'vertical fitting' --- we do each spot by itself, but 
            # fit all verticals in parallel

            # collect list of unique emission angles            
            emangles = [l.emangle for l in self.portraits[pi].lines]
            # turn into array, transpose and squeeze
            emangles = np.squeeze(np.array( emangles ).T)

            # evaluate cosine-fit at these em_angles, on a grid of ex_angles:
            fitintensities = np.array( [l.cosValue( self.parent.excitation_angles_grid ) \
                                            for l in self.portraits[pi].lines] )

            phase, I0, M, resi, fit, rawfitpars, mm = self.parent.cos_fitter( emangles, fitintensities, \
                                                                           self.parent.Nphases_for_cos_fitter )
            # store vertical fit params
            self.portraits[pi].vertical_fit_params = [ phase, I0, M, resi, mm ]

    def findModDepths(self):
        sam = self.recover_average_portrait_matrix()
        self.proj_ex = np.mean( sam, axis=0 ).reshape((sam.shape[1],1))
        self.proj_em = np.mean( sam, axis=1 ).reshape((sam.shape[0],1))

        # fitting
        ph_ex, I_ex, M_ex, r_ex, fit_ex, rawfitpars_ex, mm = self.parent.cos_fitter( self.parent.excitation_angles_grid, self.proj_ex, self.parent.Nphases_for_cos_fitter )
        ph_em, I_em, M_em, r_em, fit_em, rawfitpars_em, mm = self.parent.cos_fitter( self.parent.emission_angles_grid, self.proj_em, self.parent.Nphases_for_cos_fitter )

        # assignment
        LS = ph_ex - ph_em
        if LS > np.pi/2:  LS -= np.pi
        if LS < -np.pi/2: LS += np.pi
        self.phase_ex = ph_ex[0]
        self.M_ex     = M_ex[0]
        self.phase_em = ph_em[0]
        self.M_em     = M_em[0]
        self.LS       = LS[0]
        # store in coverage maps
        self.parent.M_ex_image[ self.coords[1]:self.coords[3]+1, self.coords[0]:self.coords[2]+1 ] = self.M_ex
        self.parent.M_em_image[ self.coords[1]:self.coords[3]+1, self.coords[0]:self.coords[2]+1 ] = self.M_em
        self.parent.phase_ex_image[ self.coords[1]:self.coords[3]+1, self.coords[0]:self.coords[2]+1 ] = self.phase_ex
        self.parent.phase_em_image[ self.coords[1]:self.coords[3]+1, self.coords[0]:self.coords[2]+1 ] = self.phase_em
        self.parent.LS_image[ self.coords[1]:self.coords[3]+1, self.coords[0]:self.coords[2]+1 ] = self.LS


    # def cos_fit_and_find_mod_depths(self):
    #     self.residual = 0

    #     # we assume that the number of portraits and lines is the same 
    #     # for all spots (can't think of a reason why that shouldn't be the case).
    #     Nportraits = len(self.portraits)
    #     Nlines     = len(self.portraits[0].lines )

    #     # for each portrait ---- outermost loop, we do portraits in series
    #     for pi in range(Nportraits):
    #         # part I, 'horizontal fitting' of the lines of constant emission angles

    #         # for each line ---- we do lines in series, __but all spots in parallel__:
    #         for li in range(Nlines):

    #             # get excitation angle array (same for all spots!)
    #             exangles    = self.portraits[pi].lines[li].exangles

    #             # create list of intensity arrays (one array for each spot)
    #             intensities = self.portraits[pi].lines[li].intensities

    #             # turn into numpy array and make sure it's a column
    #             intensities = np.array( intensities ).reshape((exangles.size,1))

    #             exa = exangles.copy()

    #             phase, I0, M, resi, fit, rawfitpars, mm = self.parent.cos_fitter( exa, intensities, \
    #                                                                            self.parent.Nphases_for_cos_fitter ) 
    #             # write cosine parameters into line object
    #             self.portraits[pi].lines[li].set_fit_params( phase, I0, M, resi )
    #             # and add residual
    #             self.residual += resi


    #         # part II, 'vertical fitting' --- we do each spot by itself, but 
    #         # fit all verticals in parallel

    #         # collect list of unique emission angles            
    #         emangles = [l.emangle for l in self.portraits[pi].lines]
    #         # turn into array, transpose and squeeze
    #         emangles = np.squeeze(np.array( emangles ).T)

    #         # evaluate cosine-fit at these em_angles, on a grid of ex_angles:
    #         fitintensities = np.array( [l.cosValue( self.parent.excitation_angles_grid ) \
    #                                         for l in self.portraits[pi].lines] )

    #         phase, I0, M, resi, fit, rawfitpars, mm = self.parent.cos_fitter( emangles, fitintensities, \
    #                                                                        self.parent.Nphases_for_cos_fitter )
    #         # store vertical fit params
    #         self.portraits[pi].vertical_fit_params = [ phase, I0, M, resi, mm ]

    #         # sam += [ rawfitpars[0,i]+rawfitpars[1,i]*self.parent.precomputed_cosines[mm[i]] \
    #         #              for i in range(len(mm)) ]


    #     sam = self.recover_average_portrait_matrix()
    #     self.proj_ex = np.mean( sam, axis=0 ).reshape((sam.shape[1],1))
    #     self.proj_em = np.mean( sam, axis=1 ).reshape((sam.shape[0],1))

    #     # fitting
    #     ph_ex, I_ex, M_ex, r_ex, fit_ex, rawfitpars_ex, mm = self.parent.cos_fitter( self.parent.excitation_angles_grid, self.proj_ex, self.parent.Nphases_for_cos_fitter )
    #     ph_em, I_em, M_em, r_em, fit_em, rawfitpars_em, mm = self.parent.cos_fitter( self.parent.emission_angles_grid, self.proj_em, self.parent.Nphases_for_cos_fitter )

    #     # assignment
    #     LS = ph_ex - ph_em
    #     if LS > np.pi/2:  LS -= np.pi
    #     if LS < -np.pi/2: LS += np.pi
    #     self.phase_ex = ph_ex[0]
    #     self.M_ex     = M_ex[0]
    #     self.phase_em = ph_em[0]
    #     self.M_em     = M_em[0]
    #     self.LS       = LS[0]
    #     # store in coverage maps
    #     self.parent.M_ex_image[ self.coords[1]:self.coords[3]+1, self.coords[0]:self.coords[2]+1 ] = self.M_ex
    #     self.parent.M_em_image[ self.coords[1]:self.coords[3]+1, self.coords[0]:self.coords[2]+1 ] = self.M_em
    #     self.parent.phase_ex_image[ self.coords[1]:self.coords[3]+1, self.coords[0]:self.coords[2]+1 ] = self.phase_ex
    #     self.parent.phase_em_image[ self.coords[1]:self.coords[3]+1, self.coords[0]:self.coords[2]+1 ] = self.phase_em
    #     self.parent.LS_image[ self.coords[1]:self.coords[3]+1, self.coords[0]:self.coords[2]+1 ] = self.LS


class Portrait:
    def __init__( self, exangles, emangles, intensities, parent ):
        self.exangles = exangles
        self.emangles = emangles
        self.intensities = intensities
        self.parent = parent
        self.lines = []


        # print '=== portrait ==='
        # print exangles
        # print emangles
        # print intensities

        # import matplotlib.pyplot as plt
        # plt.interactive(True)
        # plt.figure()
        # plt.plot( exangles, intensities )
        # plt.draw()
        # import time
        # time.sleep(1)
        
#        self.vector = np.array( (self.exangles, self.emangles, self.intensities) ).T
        self.split_into_emission_lines()
        del(self.intensities)

    def split_into_emission_lines( self ):
        """Splits the portrait into the flat emission parts."""
    
        # edge 'detection' to work out where emission angles change
        edges = (np.diff(self.emangles)!=0).nonzero()[0]
        # extend the array: a zero on the left because we know that the
        # first frame is an edge, and a p.shape[0] on the right because
        # we know that the last frame is an edge as well.
        edges = np.concatenate( (np.array( [0] ), edges+1, np.array([self.exangles.shape[0]]) ) )

        # grab the angles and intensities associated with a line, where by 'line'
        # we mean data points for which emission angles do not change (but excitation 
        # does!)
        lines = []
        for i in range(edges.size-1):
            exangles  = self.exangles[edges[i]:edges[i+1]]
            intensity = self.intensities[edges[i]:edges[i+1]]
            emangles  = self.emangles[edges[i]:edges[i+1]]
        
            # test that this is really one emission line (no change in 
            # emission angles)
            assert np.unique( emangles ).size == 1

            l = Line( exangles, intensity, np.unique(emangles) )

            # append line to list of lines
            lines.append( l )
#        lines.append( np.array((exangles, intensity)).T )

        # did we lose any data rows due to our funky indexing?
        assert np.sum( [lines[i].exangles.shape[0] for i in range(len(lines))] ) == self.exangles.shape[0]
    
        self.lines = lines

    def show_portrait_matrix( self ):
        plt.matshow( self.matrix, origin='bottom')
        plt.plot( [0,180], [0,180], 'k-' )
        plt.xlim( 0, 180 )
        plt.ylim( 0, 180 )


    def recover_portrait_matrix(self):
        # print dir(self)
        mycos = lambda a, ph, I, M: I*( 1+M*( np.cos(2*(a-ph)) ) )

        # print self.vertical_fit_params
        # print self.vertical_fit_params[0].shape

        phase = self.vertical_fit_params[0]
        I0    = self.vertical_fit_params[1]
        M     = self.vertical_fit_params[2]

        # mm    = self.vertical_fit_params[4]

        # pic2 = []
        # for exi in range( self.parent.parent.excitation_angles_grid.size ):
        #     pic2.append( I0[exi]*(1+M[exi]*self.parent.parent.precomputed_cosines[mm[exi]]) )
        # return np.array(pic).T

        pic = np.zeros( (self.parent.parent.emission_angles_grid.size, self.parent.parent.excitation_angles_grid.size) )
        for exi in range( self.parent.parent.excitation_angles_grid.size ):
            pic[:,exi] = mycos( self.parent.parent.emission_angles_grid, phase[exi], I0[exi], M[exi] )

        return pic

#                     s.averagematrix += pic
# #                    s.portraits[pi].matrix = pic

#         for s in self.validspots:
#             s.averagematrix /= Nportraits
#             s.residual /= Nportraits
        #self.spots[si].portraits[pi].vertical_fit_params = [phase, I0, M, resi]



class Line:
    def __init__( self, exangles, intensities, emangle ):
        self.exangles = exangles
        self.intensities = intensities
        self.emangle = emangle

        # import matplotlib.pyplot as plt
        # plt.interactive(True)
        # plt.figure()
        # plt.plot( exangles, intensities )
        # plt.draw()
        # import time
        # time.sleep(1)


    def set_fit_params( self, phase, I0, M0, residuals ):
        self.phase = phase
        self.I0 = I0
        self.M0 = M0
        self.resi = residuals
        
    def cosValue( self, angle ):
        return self.I0 * ( 1+self.M0*np.cos( 2*(angle-self.phase) ) )





