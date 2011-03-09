# -*- coding: utf-8 -*-
"""
Created on Wed Oct 06 09:48:42 2010

"""
import numpy as np
import scipy as sp
import scipy.interpolate
import enthought.traits.api as t
import enthought.traits.ui.api as tui 

import messages
import new_coordinates
import file_io
import drawing
import utils
import types
import copy

class Parameters(object):
    '''
    A class to comfortable access some parameters as attributes'''
    def __init__(self, dictionary):
        self.load_from_dictionary(dictionary)
        
    def load_from_dictionary(self, dictionary):
        for key, value in dictionary.iteritems():
            self.__setattr__(key, value)
 
    def print_items(self):
        '''Prints only the attributes that are not methods'''
        for item in self.__dict__.items():
            if type(item) != types.MethodType:
                print("%s = %s") % item


class Signal(t.HasTraits):
    data = t.Array()
    coordinates = t.Instance(new_coordinates.CoordinatesManager)
    extra_parameters = t.Dict()
    parameters = t.Instance(Parameters)
    name = t.Str('')
    units = t.Str()
    scale = t.Float(1)
    offset = t.Float(0)
    physical_property = t.Str()
    def __init__(self, dictionary):
        '''All data interaction is made through this class or its subclasses
            
        
        Parameters:
        -----------
        dictionary : dictionary
           see load_dictionary for the format
        '''    
        super(Signal, self).__init__()
        self.load_dictionary(dictionary)
        self._plot = None
        self._shape_before_unfolding = None
        
    def load_dictionary(self, dictionary, parameters = Parameters):
        '''
        Parameters:
        -----------
        dictionary : dictionary
            A dictionary containing at least a 'data' keyword with an array of 
            arbitrary dimensions. Additionally the dictionary can contain the 
            following keys:
                coordinates: a dictionary that defines the coordinates (see the 
                    CoordiantesManager class)
                attributes: a dictionary which keywords are stored as attributes 
                of the signal class
                parameters: a dictionary containing a set of parameters that 
                    will be stored as attributes of a Parameters class. 
                    For some subclasses some particular parameters might be 
                    mandatory.
                extra_parameters: a dictionary that will be accesible in the 
                    extra_parameters attribute of the signal class and that 
                    tipycally contains all the parameters that has been imported
                    from the original data file.
        parameters : a Parameters class or subclass 
        '''
        self.data = dictionary['data']
        if not dictionary.has_key('coordinates'):
            dictionary['coordinates'] = self._get_undefined_coordinates_list()
        self.coordinates = new_coordinates.CoordinatesManager(
        dictionary['coordinates'])
        if not dictionary.has_key('parameters'):
            dictionary['parameters'] = {}
        if not dictionary.has_key('extra_parameters'):
            dictionary['extra_parameters'] = {}
        if dictionary.has_key('attributes'):
            for key, value in dictionary['attributes'].iteritems():
                self.__setattr__(key, value)
        self.parameters = parameters(dictionary['parameters'])
        self.extra_parameters = dictionary['extra_parameters']
        
    def _get_undefined_coordinates_list(self):
        coordinates = []
        for i in range(len(self.data.shape)):
            coordinates.append(
            {'name' : 'undefined',
            'scale' : 1.,
            'offset' : 0.,
            'size' : int(self.data.shape[i]),
            'units' : 'undefined',
            'index_in_array' : i,})
        return coordinates
        
    def __call__(self, coordinates = None):
        if coordinates is None:
            coordinates = self.coordinates
        return self.data.__getitem__(coordinates._getitem_tuple)
        
    def is_spectrum_line(self):
        if len(self.data.squeeze().shape) == 2:
            return True
        else:
            return False
        
    def is_spectrum_image(self):
        if len(self.data.squeeze().shape) == 3:
            return True
        else:
            return False
        
    def is_single_spectrum(self):
        if len(self.data.squeeze().shape) == 1:
            return True
        else:
            return False
    
    # TODO: This one needs some care    
    def get_image(self, spectral_range = slice(None), background_range = None):
        data = self.data
        if self.is_spectrum_line() is True:
            return self.data.squeeze()
        elif self.is_single_spectrum() is True:
            return None
        if background_range is not None:
            bg_est = utils.two_area_powerlaw_estimation(self, 
                                                        background_range.start, 
                                                        background_range.stop, )
            A = bg_est['A'][np.newaxis,:,:]
            r = bg_est['r'][np.newaxis,:,:]
            E = self.energy_axis[spectral_range,np.newaxis,np.newaxis]
            bg = A*E**-r
            return (data[spectral_range,:,:] - bg).sum(0)
        else:
            return data[..., spectral_range].sum(-1)
    
    def plot(self, coordinates = None):
        if coordinates is None:
            coordinates = self.coordinates
        if coordinates.output_dim == 1:
            # Hyperspectrum
            if self._plot is not None:
#            if self.coordinates is not self.hse.coordinates:
                try:
                    self._plot.close()
                except:
                    # If it was already closed it will raise an exception,
                    # but we want to carry on...
                    pass
                
                self.hse = None
            self._plot = drawing.mpl_hse.MPL_HyperSpectrum_Explorer()
            self._plot.spectrum_data_function = self.__call__
            self._plot.spectrum_title = self.name
            self._plot.xlabel = '%s (%s)' % (
                self.coordinates.coordinates[-1].name, 
                self.coordinates.coordinates[-1].units)
            self._plot.ylabel = 'Intensity'
            self._plot.coordinates = coordinates
            self._plot.axis = self.coordinates.coordinates[-1].axis
            
            # Image properties
            self._plot.image_data_function = self.get_image
            self._plot.image_title = ''
            self._plot.pixel_size = self.coordinates.coordinates[0].scale
            self._plot.pixel_units = self.coordinates.coordinates[0].units
            
        elif coordinates.output_dim == 2:
            self._plot = drawing.mpl_ise.MPL_HyperImage_Explorer()
        else:
            messages.warning_exit('Plotting is not supported for this view')
        
        self._plot.plot()
        
    traits_view = tui.View(
        tui.Item('name'),
        tui.Item('physical_property'),
        tui.Item('units'),
        tui.Item('offset'),
        tui.Item('scale'),)
    
    def save(self, filename, **kwds):
        '''Saves the signal in the specified format.
        
        The function gets the format from the extension. You can use:
            - hdf5 for HDF5
            - nc for NetCDF
            - msa for EMSA/MSA single spectrum saving.
            - bin to produce a raw binary file
        
        Parameters
        ----------
        filename : str
        msa_format : {'Y', 'XY'}
            'Y' will produce a file without the energy axis. 'XY' will also 
            save another column with the energy axis. For compatibility with 
            Gatan Digital Micrograph 'Y' is the default.
        '''
        file_io.save(filename, self, **kwds)
        
    def _replot(self):
        if self._plot is not None:
            if self._plot.is_active() is True:
                self.plot()
                
    def get_dimensions_from_data(self):
        '''Get the dimension parameters from the data_cube. Useful when the 
        data_cube was externally modified, or when the SI was not loaded from
        a file
        '''
        dc = self.data
        for coordinate in self.coordinates.coordinates:
            coordinate.size = int(dc.shape[coordinate.index_in_array])
            print("%s size: %i" % 
            (coordinate.name, dc.shape[coordinate.index_in_array]))
        self._replot()
        
    # Transform ________________________________________________________________
        
    def crop_in_pixels(self, axis, i1 = None, i2 = None):
        '''Crops the data in a given axis. The range is given in pixels
        axis : int
        i1 : int
            Start index
        i2 : int
            End index
            
        See also:
        ---------
        crop_in_units
        '''
        axis = self._get_positive_axis(axis)
        if i1 is not None:
            new_offset = self.coordinates.coordinates[axis].axis[i1]
        # We take a copy to guarantee the continuity of the data
        self.data = self.data[
        (slice(None),)*axis + (slice(i1, i2), Ellipsis)].copy()
        
        if i1 is not None:
            self.coordinates.coordinates[axis].offset = new_offset
        self.get_dimensions_from_data()      
        
    def crop_in_units(self, axis, x1 = None, x2 = None):
        '''Crops the data in a given axis. The range is given in the units of 
        the axis
         
        axis : int
        i1 : int
            Start index
        i2 : int
            End index
            
        See also:
        ---------
        crop_in_pixels
        
        '''
        i1 = self.coordinates.coordinates[axis].value2index(x1)
        i2 = self.coordinates.coordinates[axis].value2index(x2)
        self.crop_in_pixels(axis, i1, i2)
        
    def roll_xy(self, n_x, n_y = 1):
        '''Roll over the x axis n_x positions and n_y positions the former rows
        
        This method has the purpose of "fixing" a bug in the acquisition of the
        Orsay's microscopes and probably it does not have general interest
        
        Parameters
        ----------
        n_x : int
        n_y : int
        
        Note: Useful to correct the SI column storing bug in Marcel's 
        acquisition routines.
        '''
        self.data = np.roll(self.data, n_x, 0)
        self.data[:n_x,...] = np.roll(self.data[:n_x,...],n_y,1)
        self._replot()

    # TODO: After using this function the plotting does not work  
    def swap_axis(self, axis1, axis2):
        '''Swaps the axes
        
        Parameters
        ----------
        axis1 : positive int
        axis2 : positive int        
        '''
        self.data = self.data.swapaxes(axis1,axis2)
        c1 = self.coordinates.coordinates[axis1]
        c2 = self.coordinates.coordinates[axis2]
        c1.index_in_array, c2.index_in_array =  \
            c2.index_in_array, c1.index_in_array
        self.coordinates.coordinates[axis1] = c2
        self.coordinates.coordinates[axis2] = c1
        self.coordinates.set_output_dim()
        self._replot()
        
    def rebin(self, new_shape):
        '''
        Rebins the SI to the new shape
        
        Parameters
        ----------
        new_shape: tuple of int of dimension 3
        '''
        factors = np.array(self.data.shape) / np.array(new_shape)
        self.data = utils.rebin(self.data,new_shape)
        for coordinate in self.coordinates.coordinates:
            coordinate.scale *= factors[coordinate.index_in_array]
        self.get_dimensions_from_data()
             
    def split_in(self, axis, number_of_parts = None, steps = None):
        '''Splits the data
        
        The split can be defined either by the `number_of_parts` or by the 
        `steps` size.
        
        Parameters
        ----------
        number_of_parts : int or None
            Number of parts in which the SI will be splitted
        steps : int or None
            Size of the splitted parts
        axis : int
            The splitting axis
            
        Return
        ------
        tuple with the splitted signals
        '''
        axis = self._get_positive_axis(axis)
        if number_of_parts is None and steps is None:
            if not self._splitting_steps:
                messages.warning_exit(
                "Please provide either number_of_parts or a steps list")
            else:
                steps = self._splitting_steps
                print "Splitting in ", steps
        elif number_of_parts is not None and steps is not None:
            print "Using the given steps list. number_of_parts dimissed"
        splitted = []
        shape = self.data.shape
        
        if steps is None:
            rounded = (shape[axis] - (shape[axis] % number_of_parts))
            step =  rounded / number_of_parts
            cut_node = range(0,rounded+step,step)
        else:
            cut_node = np.array([0] + steps).cumsum()
        for i in range(len(cut_node)-1):
            data = self.data[
            (slice(None),)*axis + (slice(cut_node[i],cut_node[i+1]), Ellipsis)]
            s = Signal({'data' : data})
            # TODO: When copying plotting does not work
#            s.coordinates = copy.deepcopy(self.coordinates)
            s.get_dimensions_from_data()
            splitted.append(s)
        return splitted

    # TODO: there is a bug when plotting if in a SI unfolded_axis = 0
    def unfold(self, steady_axis = -1, unfolded_axis = -2):
        if len(self.data.squeeze().shape) < 3: return
        self._shape_before_unfolding = self.data.shape
        self._coordinates_before_unfolding = self.coordinates
        new_shape = [1] * len(self.data.shape)
        new_shape[steady_axis] = self.data.shape[steady_axis]
        new_shape[unfolded_axis] = -1
        self.data = self.data.reshape(new_shape).squeeze()
        self.coordinates = new_coordinates.CoordinatesManager(
        self._get_undefined_coordinates_list())
        if steady_axis > unfolded_axis:
            index = 1
        else:
            index = 0
        nc = self.coordinates.coordinates[
        steady_axis].get_coordinate_dictionary()
        nc['index_in_array'] = index 
        # TODO: get some coordinates data
        self.coordinates.coordinates[index].__init__(
       **nc)
        self.coordinates.coordinates[index].slice = slice(None)
        self.coordinates.coordinates[index - 1].slice = None
        self._replot()            
            
    def fold(self):
        '''If the SI was previously unfolded, folds it back'''
        if self._shape_before_unfolding is not None:
            self.data = self.data.reshape(self._shape_before_unfolding)
            self.coordinates = self._coordinates_before_unfolding
            self._shape_before_unfolding = None
            self._coordinates_before_unfolding = None
            self._replot()

    def _get_positive_axis(self, axis):
        if axis < 0:
            axis = len(self.data.shape) + axis
        return axis

    def correct_bad_pixels(self, indexes, axis = -1):
        '''Substitutes the value of a given pixel by the average of the 
        adjencent pixels
        
        Parameters
        ----------
        indexes : tuple of int
        axis : -1
        '''
        axis = self._get_positive_axis(axis)
        data = self.data
        for pixel in indexes:
            data[(slice(None),)*axis + (pixel, Ellipsis)] = \
            (data[(slice(None),)*axis + (pixel - 1, Ellipsis)] + \
            data[(slice(None),)*axis + (pixel + 1, Ellipsis)]) / 2.
        self._replot()
        
        
    def align_with_array_1D(self, shift_array, axis = -1, 
                            interpolation_method = 'linear'):
        '''Shift each one dimensional object by the amount specify by a given 
        array
        
        Parameters
        ----------
        shift_map : numpy array
            The shift is specify in the units of the selected axis
        interpolation_method : str or int
            Specifies the kind of interpolation as a string ('linear',
            'nearest', 'zero', 'slinear', 'quadratic, 'cubic') or as an integer
            specifying the order of the spline interpolator to use.
        '''
        
        axis = self._get_positive_axis(axis)
        ss = list(shift_array.shape)
        ss.insert(axis,1)
        shift_array = shift_array.reshape(ss).copy()
        coord = self.coordinates.coordinates[axis]
        offset = coord.offset
        _axis = coord.axis.copy()
        from progressbar import progressbar
        maxval = np.cumprod(ss)[-1] - 1
        pbar = progressbar(maxval = maxval)
        i = 0
        for dat, shift in zip(self.iterate_axis(axis), 
                              utils.iterate_axis(shift_array, axis)):
                si = sp.interpolate.interp1d(_axis ,dat, 
                                             bounds_error = False, 
                                             fill_value = 0., 
                                             kind = interpolation_method)
                coord.offset = offset + shift[0]
                dat[:] = si(coord.axis)
                pbar.update(i)
                i += 1
        coord.offset = offset
        
        # Cropping time
        mini, maxi = shift_array.min(), shift_array.max()
        if mini < 0:
            self.crop_in_units(axis, offset - mini)
        if maxi > 0:
            self.crop_in_units(axis, None, _axis[-1] - maxi)

    def iterate_axis(self, axis = -1):
        # We make a copy to guarantee that the data in contiguous, otherwise
        # it will not return a view of the data
        utils.iterate_axis(self.data, axis)
        axis = self._get_positive_axis(axis)
        unfolded_axis = axis - 1
        new_shape = [1] * len(self.data.shape)
        new_shape[axis] = self.data.shape[axis]
        new_shape[unfolded_axis] = -1
        # Warning! if the data is not contious it will make a copy!!
        data = self.data.reshape(new_shape)
        for i in range(data.shape[unfolded_axis]):
            getitem = [0] * len(data.shape)
            getitem[axis] = slice(None)
            getitem[unfolded_axis] = i
            yield(data[getitem])
#
#    def interpolate_1D(self, axis, E1, E2, xch = 20, kind = 3):
#        dc = self.data
#        ix1 = self.energy2index(E1)
#        ix2 = self.energy2index(E2)
#        ix0 = np.clip(ix1 - xch, 0, np.inf)
#        ix3 = np.clip(ix2 + xch, 0, len(self.energy_axis)+1)
#        for iy in range(dc.shape[2]):
#            for ix in range(dc.shape[1]):
#                sp = interp1d(range(ix0,ix1) + range(ix2,ix3),
#                dc[ix0:ix1,ix,iy].tolist() + dc[ix2:ix3,ix,iy].tolist(), 
#                kind = kind)
#                dc[ix1:ix2, ix, iy] = sp(range(ix1,ix2))
#        
#    def _interpolate_spectrum(self,ip, (ix,iy)):
#        data = self.data_cube
#        ch = self.data_cube.shape[0]
#        old_ax = np.linspace(0, 100,ch)
#        new_ax = np.linspace(0, 100,ch*ip - (ip-1))
#        sp = interp1d(old_ax,data[:,ix,iy])
#        return sp(new_ax)
#    
#    def align_1D(self, energy_range = (None,None), 
#    reference_spectrum_coordinates = (0,0), max_energy_shift = None, 
#    sync_SI = None, interpolate = True, interp_points = 5, progress_bar = True):
#        ''' Align the SI by cross-correlation.
#                
#        Parameters
#        ----------
#        energy_range : tuple of floats (E1, E2)
#            Restricts to the given range the area of the spectrum used for the 
#            aligment.
#        reference_spectrum_coordinates : tuple of int (x_coordinate, y_coordinate)
#            The coordianates of the spectrum that will be taken as a reference
#            to align them all
#        max_energy_shift : float
#            The maximum energy shift permitted
#        sync_SI: Spectrum instance
#            Another spectrum instance to align with the same calculated energy 
#            shift
#        interpolate : bool
#        interp_points : int
#            Number of interpolation points. Warning: making this number too big 
#            can saturate the memory   
#        '''
#        
#        print "Aligning the SI"
#        ip = interp_points + 1
#        data = self.data_cube
#        channel_1 = self.energy2index(energy_range[0])
#        channel_2 = self.energy2index(energy_range[1])
#        ch, size_x, size_y = data.shape
#        channels , size_x, size_y = data.shape
#        channels = channel_2 - channel_1
#        shift_map = np.zeros((size_x, size_y))
#        ref_ix, ref_iy = reference_spectrum_coordinates
#        if channel_1 is not None:
#            channel_1 *= ip
#        if channel_2 is not None:
#            channel_2 = np.clip(np.array(channel_2 * ip),a_min = 0, 
#            a_max = ch*ip-2)
#        if interpolate:
#            ref = self._interpolate_spectrum(ip, 
#            (ref_ix, ref_iy))[channel_1:channel_2]
#        else:
#            ref = data[channel_1:channel_2, ref_ix, ref_iy]
#        print "Calculating the shift"
#        
#        if progress_bar is True:
#            from progressbar import progressbar
#            maxval = max(1,size_x) * max(1,size_y)
#            pbar = progressbar(maxval = maxval)
#        for iy in range(size_y):
#            for ix in range(size_x):
#                if progress_bar is True:
#                    i = (ix + 1)*(iy+1)
#                    pbar.update(i)
#                if interpolate:
#                    dc = self._interpolate_spectrum(ip, (ix, iy))
#                shift_map[ix,iy] = np.argmax(np.correlate(ref, 
#                dc[channel_1:channel_2],'full')) - channels + 1
#        if progress_bar is True:
#            pbar.finish()
#        if np.min(shift_map) < 0:
#            shift_map -= np.min(shift_map)
#        if max_energy_shift:
#            max_index = self.energy2index(max_energy_shift)
#            if interpolate:
#                max_index *= ip
#            shift_map.clip(a_max = max_index)
#            
#        def apply_correction(spectrum):
#            data = spectrum.data_cube
#            print "Applying the correction"
#            if progress_bar is True:
#                maxval = max(1,size_x) * max(1,size_y)
#                pbar = progressbar(maxval = maxval)
#            for iy in range(size_y):
#                for ix in range(size_x):
#                    if progress_bar is True:
#                        i = (ix + 1)*(iy+1)
#                        pbar.update(i)
#
#                    if interpolate:
#                        sp = spectrum._interpolate_spectrum(ip, (ix, iy))
#                        data[:,ix,iy] = np.roll(sp, 
#                        int(shift_map[ix,iy]), axis = 0)[::ip]
#                        spectrum.updateenergy_axis()
#                    else:
#                        data[:,ix,iy] = np.roll(data[:,ix,iy], 
#                        int(shift_map[ix,iy]), axis = 0)
#            if progress_bar is True:
#                pbar.finish()
#            spectrum.__new_cube(data, 'alignment by cross-correlation')
#            if interpolate is True:
#                spectrum.energy_crop(shift_map.max()/ip)
#            else:
#                spectrum.energy_crop(shift_map.max())
#        apply_correction(self)
#
#        if sync_SI is not None:
#            apply_correction(sync_SI)
#
#        return shift_map
#        
#    def sum_every_n(self,n):
#        '''Bin a line spectrum
#        
#        Parameters
#        ----------
#        step : float
#            binning size
#        
#        Returns
#        -------
#        Binned line spectrum
#        
#        See also
#        --------
#        sum_every
#        '''
#        dc = self.data_cube
#        if dc.shape[1] % n != 0:
#            messages.warning_exit(
#            "n is not a divisor of the size of the line spectrum\n"
#            "Try giving a different n or using sum_every instead")
#        size_list = np.zeros((dc.shape[1] / n))
#        size_list[:] = n
#        return self.sum_every(size_list)
#    
#    def sum_every(self,size_list):
#        '''Sum a line spectrum intervals given in a list and return the 
#        resulting SI
#        
#        Parameters
#        ----------
#        size_list : list of floats
#            A list of the size of each interval to sum.
#        
#        Returns
#        -------
#        SI
#        
#        See also
#        --------
#        sum_every_n
#        '''
#        dc = self.data_cube
#        dc_shape = self.data_cube.shape
#        if np.sum(size_list) != dc.shape[1]:
#            messages.warning_exit(
#            "The sum of the elements of the size list is not equal to the size" 
#            " of the line spectrum")
#        new_dc = np.zeros((dc_shape[0], len(size_list), 1))
#        ch = 0
#        for i in range(len(size_list)):
#            new_dc[:,i,0] = dc[:,ch:ch + size_list[i], 0].sum(1)
#            ch += size_list[i]
#        sp = Spectrum()
#        sp.data_cube = new_dc
#        sp.get_dimensions_from_cube()
#        return sp
#        
#    def sum(self, axis):
#        '''Sum the SI over the given axis
#        
#        Parameters
#        ----------
#        axis : int
#        '''
#        dc = self.data_cube
#        dc = dc.sum(axis)
#        dc = dc.reshape(list(dc.shape) + [1,])
#        self.data_cube = dc
#        self.get_dimensions_from_cube()
#
#    def mean(self, axis):
#        '''Average the SI over the given axis
#        
#        Parameters
#        ----------
#        axis : int
#        '''
#        dc = self.data_cube
#        dc = dc.mean(axis)
#        dc = dc.reshape(list(dc.shape) + [1,])
#        self.data_cube = dc
#        self.get_dimensions_from_cube()
#        
#    def roll(self, axis = 2, shift = 1):
#        '''Roll the SI. see numpy.roll
#        
#        Parameters
#        ----------
#        axis : int
#        shift : int
#        '''
#        self.data_cube = np.roll(self.data_cube, shift, axis)
#        self._replot()
#        
#    def sum_in_mask(self, mask):
#        '''Returns the result of summing all the spectra in the mask.
#        
#        Parameters
#        ----------
#        mask : boolean numpy array
#        
#        Returns
#        -------
#        Spectrum
#        '''
#        dc = self.data_cube.copy()
#        mask3D = mask.reshape([1,] + list(mask.shape)) * np.ones(dc.shape)
#        dc = (mask3D*dc).sum(1).sum(1) / mask.sum()
#        s = Spectrum()
#        s.data_cube = dc.reshape((-1,1,1))
#        s.get_dimensions_from_cube()
#        utils.copy_energy_calibration(self,s)
#        return s
#        
#    def get_calibration_from(self, s):
#        '''Copy the calibration from another Spectrum instance
#        Parameters
#        ----------
#        s : spectrum instance
#        '''
#        utils.copy_energy_calibration(s, self)
#    
#    def estimate_variance(self, dc = None, gaussian_noise_var = None):
#        '''Variance estimation supposing Poissonian noise
#        
#        Parameters
#        ----------
#        dc : None or numpy array
#            If None the SI is used to estimate its variance. Otherwise, the 
#            provided array will be used.   
#        Note
#        ----
#        The gain_factor and gain_offset from the aquisition parameters are used
#        '''
#        print "Variace estimation using the following values:"
#        print "Gain factor = ", self.acquisition_parameters.gain_factor
#        print "Gain offset = ", self.acquisition_parameters.gain_offset
#        if dc is None:
#            dc = self.data_cube
#        gain_factor = self.acquisition_parameters.gain_factor
#        gain_offset = self.acquisition_parameters.gain_offset
#        self.variance = dc*gain_factor + gain_offset
#        if self.variance.min() < 0:
#            if gain_offset == 0 and gaussian_noise_var is None:
#                print "The variance estimation results in negative values"
#                print "Maybe the gain_offset is wrong?"
#                self.variance = None
#                return
#            elif gaussian_noise_var is None:
#                print "Clipping the variance to the gain_offset value"
#                self.variance = np.clip(self.variance, np.abs(gain_offset), 
#                np.Inf)
#            else:
#                print "Clipping the variance to the gaussian_noise_var"
#                self.variance = np.clip(self.variance, gaussian_noise_var, 
#                np.Inf) 
#   
#    def calibrate(self, lcE = 642.6, rcE = 849.7, lc = 161.9, rc = 1137.6, 
#    modify_calibration = True):
#        dispersion = (rcE - lcE) / (rc - lc)
#        origin = lcE - dispersion * lc
#        print "Energy step = ", dispersion
#        print "Energy origin = ", origin
#        if modify_calibration is True:
#            self.set_new_calibration(origin, dispersion)
#        return origin, dispersion
#    
#    def _correct_spatial_mask_when_unfolded(self, spatial_mask = None,):
#        if 'unfolded' in self.history:
#            if spatial_mask is not None:
#                spatial_mask = \
#                spatial_mask.reshape((-1,), order = 'F')
#        return spatial_mask
#        
#    def get_single_spectrum(self):
#        s = Spectrum({'calibration' : {'data_cube' : self()}})
#        s.get_calibration_from(self)
#        return s
        
        
#class SignalwHistory(Signal):
#    def _get_cube(self):
#        return self.__cubes[self.current_cube]['data']
#    
#    def _set_cube(self,arg):
#        self.__cubes[self.current_cube]['data'] = arg
#    data_cube = property(_get_cube,_set_cube)
#    
#    def __new_cube(self, cube, treatment):
#        history = copy.copy(self.history)
#        history.append(treatment)
#        if self.backup_cubes:
#            self.__cubes.append({'data' : cube, 'history': history})
#        else:
#            self.__cubes[-1]['data'] = cube
#            self.__cubes[-1]['history'] = history
#        self.current_cube = -1
#        
#    def _get_history(self):
#        return self.__cubes[self.current_cube]['history']
#    def _set_treatment(self,arg):
#        self.__cubes[self.current_cube]['history'].append(arg)
#        
#    history = property(_get_history,_set_treatment)
#    
#    def print_history(self):
#        '''Prints the history of the SI to the stdout'''
#        i = 0
#        print
#        print "Cube\tHistory"
#        print "----\t----------"
#        print
#        for cube in self.__cubes:
#            print i,'\t', cube['history']
#            i+=1
#            
        
        
        
    
    
        
        
