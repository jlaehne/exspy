# -*- coding: utf-8 -*-
# Copyright © 2007 Francisco Javier de la Peña
#
# This file is part of EELSLab.
#
# EELSLab is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# EELSLab is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with EELSLab; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  
# USA

import  math
import glob
import os
from StringIO import StringIO

import numpy as np
import scipy as sp
import scipy.signal
import scipy.ndimage
import matplotlib
def import_rpy():
    try:
        import rpy
        print "rpy imported..."
    except:
        print "python-rpy is not installed"

try:
    import matplotlib.pyplot as plt
except:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
def on_window_close(figure, function):
    '''Connects a close figure signal to a given function
    
    Parameters
    ----------
    
    figure : mpl figure instance
    function : function
    '''
    window = figure.canvas.manager.window
    backend = matplotlib.get_backend()
    if backend == 'GTKAgg':
        window.connect('destroy', function)
    elif backend == 'WXAgg':
        # In linux the following code produces a segmentation fault
        # so it is enabled only for Windows
        if os.name in ['nt','dos']:
            import wx
            def function_wrapper(event):
                # This wrapper is needed for the destroying process to carry on
                # after the function call
                try:
                    window = event.GetEventObject().canvas.manager.window
                    function(window)
                except:
                    pass
                event.Skip()
            window.Bind(wx.EVT_WINDOW_DESTROY, function_wrapper)
        
#    elif matplotlib.get_backend() == 'TkAgg':
        # Tkinter does not return the window when sending the closing
        # signal. Furthermore, for some reason that I don't understand,
        # it blocks ipython. For this reason it is now disable until I find a
        # way around the problem.
#        figure.canvas.manager.window.bind("<Destroy>",function)
#    elif matplotlib.get_backend() == 'Qt4Agg':
#        from PyQt4.QtCore import SIGNAL
#        window = figure.canvas.manager.window
#        window.connect(window, SIGNAL('destroyed()'), function)
        # I don't understand the qt syntax for connecting. Therefore, it is 
        # disable until I have the time to study it.
#        

def generate_axis(origin,step,N,index=0):
    '''Creates an axis given the origin, step and number of channels
    
    Alternatively, the index of the origin channel can be specified.
    
    Parameters
    ----------
    origin : float
    step : float
    N : number of channels
    index : int
        index number of the origin
    
    Returns
    -------
    Numpy array
    '''
    return np.linspace(origin-index*step, origin+step*(N-1-index),
N)    


def two_area_powerlaw_estimation(SI, E1, E2):
    '''Estimate a power law fit by the two area method
    
    Parameters
    ----------
    SI : Spectrum instance
    E1 : float
        first point in energy units
    E2 : float
        second point in energy units
    
    Returns
    -------
    Dictionary
    keys: r, A
    '''
    
    energy2index = SI.energy2index
    i1 = energy2index(E1)
    if energy2index(E2) - i1 % 2 == 0:
        i2 = energy2index(E2)
    else :
        i2 = energy2index(E2) - 1
    E2 = SI.energy_axis[i2]
    i3 = (i2+i1) / 2
    E3 = SI.energy_axis[i3]

    I1 = SI.energyscale * np.sum(SI.data_cube[i1:i3], 0)
    I2 = SI.energyscale * np.sum(SI.data_cube[i3:i2],0)
    r = 2*np.log(I1 / I2) / math.log(E2/E1)
    k = 1 - r
    A = k * I2 / (E2**k - E3**k)
    return {'r': r, 'A': A}
    
def gaussian_estimation(SI,E1, E2):
    '''Estimates the parameters of a gaussian by calculating the moments
    
    fit = lambda t : max*exp(-(t-x)**2/(2*width**2))
    (From scipy cookbook)
    
    Parameters
    ----------
    SI : Spectrum instance
    E1 : float
        first point of the interval in energy units
    E2 : float
        second point of the interval in energy units
        
    Returns
    -------
    Dictionary.
    keys:
    origin : float
    FWHM : float
    height : float 
    '''
    i1 = SI.energy2index(E1)
    i2 = SI.energy2index(E2)
    data = np.swapaxes(np.swapaxes(SI.data_cube[i1:i2],0,1),1,2)
    X = SI.energy_axis[i1:i2]
    x = np.sum(X*data, 2)/np.sum(data, 2)
    width = np.sqrt(np.abs(sum((X-x)**2*data, 2)/sum(data, 2)))
    max = data.max()
    return {'origin': x, 'FWHM': width, 'height': max}

def check_cube_dimensions(sp1, sp2, warn = True):
    '''Checks if the given SIs has the same dimensions.
    
    Parameters
    ----------
    sp1, sp2 : Spectrum instances
    warn : bool
        If True, produce a warning message if the SIs do not have the same 
        dimensions    
    Returns
    -------
    Boolean
    '''
    if sp1.data_cube.shape == sp2.data_cube.shape:
        return True
    else:
        if warn:
            print \
            "The given SI objects do not have the same cube dimensions"
        return False

def check_energy_dimensions(sp1, sp2, warn = True, sp2_name = None):
    '''Checks if sp2 is a single spectrum with the same energy dimension as sp1
    
    Parameters
    ----------
    sp1, sp2 : Spectrum instances
    warn : bool
        If True, produce a warning message if the SIs do not have the same 
        dimensions 
    
    Returns
    -------
    Boolean
    '''
    sp2_dim = len(sp2.data_cube.squeeze().shape)
    sp1_Edim = sp1.data_cube.shape[0]
    sp2_Edim = sp2.data_cube.shape[0]
    
    if sp2_dim == 1:
        if sp1_Edim == sp2_Edim:
            return True
        else:
            if warn:
                print "The spectra must have the same energy dimensions"
            return False
    else:
        if warn:
            print "The %s should be unidimensional" % sp2_name
        return False

def unfold_if_2D(spectrum):
    '''Unfold the SI if it is 2D
    
    Parameters
    ----------
    spectrum : Spectrum instance
    
    Returns
    -------
    
    Boolean. True if the SI was unfolded by the function.
    '''
    if spectrum.xdimension > 1 and spectrum.ydimension > 1:
        print "Automatically unfolding the SI"
        spectrum.unfold()
        return True
    else:
        return False
    
def estimate_gain(noisy_SI, clean_SI, mask = None, pol_order = 1, 
higher_than = None):
    '''Find the scale and offset of the Poissonian noise
    
    By comparing an SI with its denoised version (i.e. by PCA), this plots an 
    estimation of the variance as a function of the number of counts and fits a 
    polynomy to the result.
    
    Parameters
    ----------
    noisy_SI, clean_SI : Spectrum instances
    mask : numpy bool array
        To define the channels that will be used in the calculation.
    pol_order : int
        The order of the polynomy.
    higher_than: float
        To restrict the fit to counts over the given value.
            
    Returns
    -------
    Dictionary with the result of a linear fit to estimate the offset and 
    scale factor
    '''
    ns = noisy_SI.data_cube.copy()
    cl = clean_SI.data_cube.copy()

    fold_back_noisy =  unfold_if_2D(noisy_SI)
    fold_back_clean =  unfold_if_2D(clean_SI)
    ns = noisy_SI.data_cube.copy()
    cs = clean_SI.data_cube.copy()
    
    if mask is not None:
        ns = ns[mask]
        cs = cs[mask]
    if check_cube_dimensions(noisy_SI, clean_SI):
        noise = ns - cs
        variance = np.var(noise, 1)
        average = np.mean(cs, 1)
        plt.figure()
        plt.scatter(average.squeeze(), variance.squeeze())
        plt.xlabel('Counts')
        plt.ylabel('Variance')
        ave = average.squeeze()
        so = np.argsort(ave)
        aveso = ave[so]
        avesoh = aveso > higher_than
        varso = variance.squeeze()[so]
        fit = np.polyfit(aveso[avesoh], varso[avesoh], pol_order)
        plt.plot(ave[so], np.polyval(fit,ave[so]))
        dic = {'fit' : fit, 'variance' : variance.squeeze(), 
        'counts' : average.squeeze()}
        return dic
    if fold_back_noisy is True:
        noisy_SI.fold()
    if fold_back_clean is True:
        clean_SI.fold()
        
def rebin(a, new_shape):
    '''Rebin SI
    
    rebin ndarray data into a smaller ndarray of the same rank whose dimensions
    are factors of the original dimensions. eg. An array with 6 columns and 4 
    rows can be reduced to have 6,3,2 or 1 columns and 4,2 or 1 rows.
    example usages:
    >>> a=rand(6,4); b=rebin(a,3,2)
    >>> a=rand(6); b=rebin(a,2)
    Adapted from scipy cookbook
    
    Parameters
    ----------
    a : numpy array
    new_shape : tuple
        shape after binning
        
    Returns
    -------
    numpy array
    '''
    shape = a.shape
    lenShape = len(shape)
    factor = np.asarray(shape)/np.asarray(new_shape)
    evList = ['a.reshape('] + \
             ['new_shape[%d],factor[%d],'%(i,i) for i in range(lenShape)] + \
             [')'] + ['.sum(%d)'%(i+1) for i in range(lenShape)]
    return eval(''.join(evList))
    
def estimate_drift(im1,im2):
    '''Estimate the drift  between two images by cross-correlation
    
    
    It preprocess the images by applying a median filter (to smooth the images) 
    and the solbi edge detection filter.
    
    Parameters
    ----------
    im1, im2 : Image instances
    
    Output
    ------
    array with the coordinates of the translation of im2 in respect to im1.
    '''
    print "Estimating the spatial drift"
    im1 = im1.data_cube.squeeze()
    im2 = im2.data_cube.squeeze()
    # Apply a "denoising filter" and edge detection filter
    im1 = scipy.ndimage.sobel(scipy.signal.medfilt(im1))
    im2 = scipy.ndimage.sobel(scipy.signal.medfilt(im2))
    # Compute the cross-correlation
    _correlation = scipy.signal.correlate(im1,im2)
    
    shift = im1.shape - np.ones(2) - \
    np.unravel_index(_correlation.argmax(),_correlation.shape)
    print "The estimated drift is ", shift
    return shift

def savitzky_golay(data, kernel = 11, order = 4):
    """Savitzky-Golay filter
    
    Adapted from scipy cookbook http://www.scipy.org/Cookbook/SavitzkyGolay
    
    Parameters
    ----------
    data : 1D numpy array
    kernel : positiv integer > 2*order giving the kernel size - order
    order : order of the polynomial
    
    Returns
    -------
    returns smoothed data as a numpy array

    Example
    -------
    smoothed = savitzky_golay(<rough>, [kernel = value], [order = value]
    """
    try:
            kernel = abs(int(kernel))
            order = abs(int(order))
    except ValueError, msg:
        raise ValueError("kernel and order have to be of type int (floats will \
        be converted).")
    if kernel % 2 != 1 or kernel < 1:
        raise TypeError("kernel size must be a positive odd number, was: %d" 
        % kernel)
    if kernel < order + 2:
        raise TypeError(
        "kernel is to small for the polynomals\nshould be > order + 2")

    # a second order polynomal has 3 coefficients
    order_range = range(order+1)
    N = (kernel -1) // 2
    b = np.mat([[k**i for i in order_range] for k in range(-N, 
    N+1)])
    # since we don't want the derivative, else choose [1] or [2], respectively
    m = np.linalg.pinv(b).A[0]
    window_size = len(m)
    N = (window_size-1) // 2

    # precompute the offset values for better performance
    offsets = range(-N, N+1)
    offset_data = zip(offsets, m)

    smooth_data = list()

    # temporary data, with padded zeros 
    # (since we want the same length after smoothing)
    # temporary data, extended with a mirror image to the left and right
    firstval=data[0]
    lastval=data[len(data)-1]
    #left extension: f(x0-x) = f(x0)-(f(x)-f(x0)) = 2f(x0)-f(x)
    #right extension: f(xl+x) = f(xl)+(f(xl)-f(xl-x)) = 2f(xl)-f(xl-x)
    leftpad=np.zeros(N)+2*firstval
    rightpad=np.zeros(N)+2*lastval
    leftchunk=data[1:1+N]
    leftpad=leftpad-leftchunk[::-1]
    rightchunk=data[len(data)-N-1:len(data)-1]
    rightpad=rightpad-rightchunk[::-1]
    data = np.concatenate((leftpad, data))
    data = np.concatenate((data, rightpad))

#    data = np.concatenate((np.zeros(N), data, np.zeros(N)))
    for i in range(N, len(data) - N):
            value = 0.0
            for offset, weight in offset_data:
                value += weight * data[i + offset]
            smooth_data.append(value)
    return np.array(smooth_data)

# Functions to calculates de savitzky-golay filter from 
def resub(D, rhs):
    """solves D D^T = rhs by resubstituion.
    D is lower triangle-matrix from cholesky-decomposition
    http://www.procoders.net
    """

    M = D.shape[0]
    x1= np.zeros((M,),float)
    x2= np.zeros((M,),float)

    # resub step 1
    for l in range(M): 
        sum_ = rhs[l]
        for n in range(l):
            sum_ -= D[l,n]*x1[n]
        x1[l] = sum_/D[l,l]

    # resub step 2
    for l in range(M-1,-1,-1): 
        sum_ = x1[l]
        for n in range(l+1,M):
            sum_ -= D[n,l]*x2[n]
        x2[l] = sum_/D[l,l]

    return x2
   

def calc_coeff(num_points, pol_degree, diff_order=0):
    '''Calculates filter coefficients for symmetric savitzky-golay filter.
    http://www.procoders.net
    see: http://www.nrbook.com/a/bookcpdf/c14-8.pdf

    num_points   means that 2*num_points+1 values contribute to the
                 smoother.

    pol_degree   is degree of fitting polynomial

    diff_order   is degree of implicit differentiation.
                 0 means that filter results in smoothing of function
                 1 means that filter results in smoothing the first 
                                             derivative of function.
                 and so on ...
    '''

    # setup normal matrix
    A = np.zeros((2*num_points+1, pol_degree+1), float)
    for i in range(2*num_points+1):
        for j in range(pol_degree+1):
            A[i,j] = math.pow(i-num_points, j)
        
    # calculate diff_order-th row of inv(A^T A)
    ATA = np.dot(A.transpose(), A)
    rhs = np.zeros((pol_degree+1,), float)
    rhs[diff_order] = 1
    D = np.linalg.cholesky(ATA)
    wvec = resub(D, rhs)

    # calculate filter-coefficients
    coeff = np.zeros((2*num_points+1,), float)
    for n in range(-num_points, num_points+1):
        x = 0.0
        for m in range(pol_degree+1):
            x += wvec[m]*pow(n, m)
        coeff[n+num_points] = x
    return coeff

def smooth(data, coeff):
    """applies coefficients calculated by calc_coeff() to signal
    http://www.procoders.net
    """
    # temporary data, extended with a mirror image to the left and right
    N = np.size(coeff-1)/2
    firstval=data[0]
    lastval=data[len(data)-1]
#    left extension: f(x0-x) = f(x0)-(f(x)-f(x0)) = 2f(x0)-f(x)
#    right extension: f(xl+x) = f(xl)+(f(xl)-f(xl-x)) = 2f(xl)-f(xl-x)
    leftpad=np.zeros(N)+2*firstval
    rightpad=np.zeros(N)+2*lastval
    leftchunk=data[1:1+N]
    leftpad=leftpad-leftchunk[::-1]
    rightchunk=data[len(data)-N-1:len(data)-1]
    rightpad=rightpad-rightchunk[::-1]
    data = np.concatenate((leftpad, data))
    data = np.concatenate((data, rightpad))
    res = np.convolve(data, coeff)
    return res[N:-N][len(leftpad):-len(rightpad)]

def sg(data, num_points, pol_degree, diff_order=0):
    '''Savitzky-Golay filter
    http://www.procoders.net
    '''
    coeff = calc_coeff(num_points, pol_degree, diff_order)
    return smooth(data, coeff)
    
def wavelet_poissonian_denoising(spectrum):
    '''Denoise data with pure Poissonian noise using wavelets
    
    Wrapper around the R packages EbayesThresh and wavethresh
    
    Parameters
    ----------
    spectrum : spectrum instance
    
    Returns
    -------
    Spectrum instance.
    '''
    import_rpy()
    rpy.r.library('EbayesThresh')
    rpy.r.library('wavethresh')
    rpy.r['<-']('X',spectrum)
    rpy.r('XHF <- hft(X)')
    rpy.r('XHFwd  <- wd(XHF, bc="symmetric")')
    rpy.r('XHFwdT  <- ebayesthresh.wavelet(XHFwd)')
    rpy.r('XHFdn  <- wr(XHFwdT)')
    XHFest = rpy.r('XHFest <- hft.inv(XHFdn)')
    return XHFest

def wavelet_gaussian_denoising(spectrum):
    '''Denoise data with pure Gaussian noise using wavelets
    
    Wrapper around the R packages EbayesThresh and wavethresh
    
    Parameters
    ----------
    spectrum : spectrum instance
    
    Returns
    -------
    Spectrum instance.
    '''
    import_rpy()
    rpy.r.library('EbayesThresh')
    rpy.r.library('wavethresh')
    rpy.r['<-']('X',spectrum)
    rpy.r('Xwd  <- wd(X, bc="symmetric")')
    rpy.r('XwdT  <- ebayesthresh.wavelet(Xwd)')
    Xdn = rpy.r('Xdn  <- wr(XwdT)')
    return Xdn

def wavelet_dd_denoising(spectrum):
    '''Denoise data with arbitraty noise using wavelets
    
    Wrapper around the R packages EbayesThresh, wavethresh and DDHFm
    
    Parameters
    ----------
    spectrum : spectrum instance
    
    Returns
    -------
    Spectrum instance.
    '''
    import_rpy()
    rpy.r.library('EbayesThresh')
    rpy.r.library('wavethresh')
    rpy.r.library('DDHFm')
    rpy.r['<-']('X',spectrum)
    rpy.r('XDDHF <- ddhft.np.2(X)')
    rpy.r('XDDHFwd  <- wd(XDDHF$hft,filter.number = 8, bc="symmetric" )')
    rpy.r('XDDHFwdT  <- ebayesthresh.wavelet(XDDHFwd)')
    rpy.r('XDDHFdn  <- wr(XDDHFwdT)')
    rpy.r('XDDHF$hft  <- wr(XDDHFwdT)')
    XHFest = rpy.r('XHFest <- ddhft.np.inv(XDDHF)')
    return XHFest

def loess(y,x = None, span = 0.2):
    '''locally weighted scatterplot smoothing
    
    Wrapper around the R funcion loess
    
    Parameters
    ----------
    spectrum : spectrum instance
    span : float
        parameter to control the smoothing
    
    Returns
    -------
    Spectrum instance.
    '''
    import_rpy()
    if x is None:
        x = np.arange(0,len(y))
    rpy.r['<-']('x',x)
    rpy.r['<-']('y',y)
    rpy.r('y.loess <- loess(y ~ x, span = %s, data.frame(x=x, y=y))' % span)
    loess = rpy.r('y.predict <- predict(y.loess, data.frame(x=x))')
    return loess

def plot_RGB_map(im_list, normalization = 'single', dont_plot = False):
    '''Plots 2 or 3 maps in RGB
    
    Parameters
    ----------
    im_list : list of Image instances
    normalization : {'single', 'global'}
    dont_plot : bool
    
    Returns
    -------
    array: RGB matrix
    '''
    from widgets import cursors
    width, height = im_list[0].data_cube.shape[:2]
    rgb = np.zeros((height, width,3))
    rgb[:,:,0] = im_list[0].data_cube.T.squeeze()
    rgb[:,:,1] = im_list[1].data_cube.T.squeeze()
    if len(im_list) == 3:
        rgb[:,:,2] = im_list[2].data_cube.T.squeeze()
    if normalization == 'single':
        for i in range(rgb.shape[2]):
            rgb[:,:,i] /= rgb[:,:,i].max()
    elif normalization == 'global':
        rgb /= rgb.max()
    rgb = rgb.clip(0,rgb.max())
    if not dont_plot:
        figure = plt.figure()
        ax = figure.add_subplot(111)
        ax.frameon = False
        ax.set_axis_off()
        ax.imshow(rgb, interpolation = 'nearest')
        cursors.add_axes(ax)
        figure.canvas.draw()
    else:
        return rgb
    
def ALS(s, thresh =.001, nonnegS = True, nonnegC = True):
    '''Alternate least squares
    
    Wrapper around the R's ALS package
    
    Parameters
    ----------
    s : Spectrum instance
    threshold : float
        convergence criteria
    nonnegS : bool
        if True, impose non-negativity constraint on the components
    nonnegC : bool
        if True, impose non-negativity constraint on the maps
    
    Returns
    -------
    Dictionary   
    '''
    import_rpy()
#    Format
#    ic format (channels, components)
#    W format (experiment, components)
#    s format (experiment, channels)
    
    nonnegS = 'TRUE' if nonnegS is True else 'FALSE'
    nonnegC = 'TRUE' if nonnegC is True else 'FALSE'
    print "Non negative constraint in the sources: ", nonnegS
    print "Non negative constraint in the mixing matrix: ", nonnegC

    refold = unfold_if_2D(s)
    W = s._calculate_recmatrix().T
    ic = np.ones(s.ic.shape)
    rpy.r.library('ALS')
    rpy.r('W = NULL')
    rpy.r('ic = NULL')
    rpy.r('d1 = NULL')
    rpy.r['<-']('d1', s.data_cube.squeeze().T)
    rpy.r['<-']('W', W)
    rpy.r['<-']('ic', ic)
    i = 0
    # Workaround a bug in python rpy version 1 
    while hasattr(rpy.r, 'test' + str(i)):
        rpy.r('test%s = NULL' % i)
        i+=1
    rpy.r('test%s = als(CList = list(W), thresh = %s, S = ic,\
     PsiList = list(d1), nonnegS = %s, nonnegC = %s)' % 
     (i, thresh, nonnegS, nonnegC))
    if refold:
        s.fold()
    exec('als_result = rpy.r.test%s' % i)
    return als_result

def snica(to_demix):
    '''Stochastic Non-negative Independent Component Analysis
    Wrapper around the SNICA ICA algorithm by Sergey Astakhov.
    http://www.klab.caltech.edu/~kraskov/MILCA/
    
    Parameters
    ---------
    to_demix : array
        spectra to demix
     
    Returns
    -------
    tuple : demixed spectra and mixing matrix    
    '''
    import snica_b
    # High temperature T=0.02 step
    y, ae = snica_b.snica_b(to_demix.T, np.eye(to_demix.shape[1]), 0.2, 0.02, 500, 10)
    # Annealing at T=1e-7
    y, ae = snica_b.snica_b(y, ae, 0.2, 1e-7, 500, 10)
    return y.T,ae

def amari(C,A):
    '''Amari test for ICA
    Adapted from the MILCA package http://www.klab.caltech.edu/~kraskov/MILCA/
    
    Parameters
    ----------
    C : numpy array
    A : numpy array
    '''
    b,a = C.shape

    dummy= np.dot(np.linalg.pinv(A),C)
    dummy = np.sum(_ntu(np.abs(dummy)),0)-1

    dummy2 = np.dot(np.linalg.pinv(C),A)
    dummy2 = np.sum(_ntu(np.abs(dummy2)),0)-1

    out=(np.sum(dummy)+np.sum(dummy2))/(2*a*(a-1))
    return out

def _ntu(C):
    m, n = C.shape
    CN = C.copy() * 0
    for t in range(n):
        CN[:,t] = C[:,t] / np.max(np.abs(C[:,t]))
    return CN

def center_and_scale(data):
    '''Center and scale SI
    
    Parameters
    ----------
    data : array
        SI
    Returns
    -------
    Dictionary:
        data : array
        invsqcovmat : array
    '''
    N = data.shape[1]
    data = data - np.average(data,0).reshape(1,-1)
    data = data.T
    covmat = np.cov(data, bias = 1)
    sqcovmat = sp.linalg.sqrtm(covmat).real
    invsqcovmat = np.linalg.inv(sqcovmat)
    data = np.dot(invsqcovmat,data)
    data = data.T
    return {'data' : data, 'invsqcovmat' : invsqcovmat}
    
def analyze_readout(spectrum):
    '''Readout diagnostic tool
    
    Parameters
    ----------
    spectrum : Spectrum instance
    
    Returns
    -------
    tuple of float : (variance, mean, normalized mean as a function of time)
    '''
    s = spectrum
    # If it is 2D, sum the first axis.
    if s.data_cube.shape[2] > 1:
        dc = s.data_cube.sum(1)
    else:
        dc = s.data_cube.squeeze()
    time_mean = dc.mean(0).squeeze()
    norm_time_mean = time_mean / time_mean.mean()
    corrected_dc = dc * (1/norm_time_mean.reshape((1,-1)))
    channel_mean = corrected_dc.mean(1)
    variance = (corrected_dc - channel_mean.reshape((-1,1))).var(0)
    return variance, channel_mean, norm_time_mean

def multi_readout_analyze(folder, ccd_height = 100., plot = True, freq = None):
    '''Analyze several readout measurements in different files for readout 
    diagnosys
    
    The readout files in dm3 format must be contained in a folder, preferentely 
    numered in the order of acquisition.
    
    Parameters
    ----------
    folder : string
        Folder where the dm3 readout files are stored
    ccd_heigh : float
    plot : bool
    freq : float
        Frequency of the camera
    
    Returns
    -------
    Dictionary
    '''    
    from spectrum import Spectrum
    files = glob.glob1(folder, '*.nc')
    if not files:
        files = glob.glob1(folder, '*.dm3')
    spectra = []
    variances = []
    binnings = []
    for f in files:
        print os.path.join(folder,f)
        s = Spectrum(os.path.join(folder,f))
        variance, channel_mean, norm_time_mean = analyze_readout(s)
        s.readout_analysis = {}
        s.readout_analysis['variance'] = variance.mean()
        s.readout_analysis['pattern'] = channel_mean
        s.readout_analysis['time'] = norm_time_mean
        if not hasattr(s,'binning'):
            s.binning = float(os.path.splitext(f)[0][1:])
            if freq:
                s.readout_frequency = freq
                s.ccd_height = ccd_height
            s.save(f)
        spectra.append(s)
        binnings.append(s.binning)
        variances.append(variance.mean())
    pixels = ccd_height / np.array(binnings)
    plt.scatter(pixels, variances, label = 'data')
    fit = np.polyfit(pixels, variances,1, full = True)
    if plot:
        x = np.linspace(0,pixels.max(),100)
        y = x*fit[0][0] + fit[0][1]
        plt.plot(x,y, label = 'linear fit')
        plt.xlabel('number of pixels')
        plt.ylabel('variance')
        plt.legend(loc = 'upper left')

    print "Variance = %s * pixels + %s" % (fit[0][0], fit[0][1])
    dictio = {'pixels': pixels, 'variances': variances, 'fit' : fit, 
    'spectra' : spectra}
    return dictio

def chrono_align(spectrum, energy_range =(None, None), axis = 1):
    '''Alignment and sum of a chrono-spim SI
    
    Parameters
    ----------
    spectrum : Spectrum intances
        Chrono-spim
    energy_range : tuple of floats
        energy interval in which to perform the alignment in energy units
    axis : int
    '''
    from spectrum import Spectrum
    dc = spectrum.data_cube.copy()
    dc_list = np.split(dc, dc.shape[axis], axis)
    final_sizes = []
#    i = 0
    for arr in dc_list:
        s = Spectrum()
        s.data_cube = arr
        s.get_dimensions_from_cube()
        s.energyscale = spectrum.energyscale
        s.energyorigin = spectrum.energyorigin
        s.updateenergy_axis()
        s.align(energy_range, result_int_factor = 2)
        final_sizes.append(s.data_cube.shape[0])
#        dc_list[i] = s.data_cube.copy()
#        i += 1

    new_size = np.min(final_sizes)
    print "New size", new_size
    for arr in dc:
        arr = arr[:new_size]
    new_dc = np.concatenate(dc_list,1)
    spectrum.data_cube = new_dc
    spectrum.get_dimensions_from_cube()

def copy_energy_calibration(from_spectrum, to_spectrum):
    '''Copy the energy calibration between two SIs
    
    Parameters
    ----------
    from_spectrum, to spectrum : Spectrum instances
    '''
    f = from_spectrum
    t = to_spectrum
    t.energyscale = f.energyscale
    t.energyorigin = f.energyorigin
    t.energyunits = f.energyunits
    t.get_dimensions_from_cube()
    t.updateenergy_axis()

def subplot_parameters(fig):
    '''Returns a list of the subplot paramters of a mpl figure
    
    Parameters
    ----------
    fig : mpl figure
    
    Returns
    -------
    tuple : (left, bottom, right, top, wspace, hspace)
    '''
    wspace = fig.subplotpars.wspace
    hspace = fig.subplotpars.hspace
    left = fig.subplotpars.left
    right = fig.subplotpars.right
    top = fig.subplotpars.top
    bottom = fig.subplotpars.bottom
    return (left, bottom, right, top, wspace, hspace)

def str2num(string, **kargs):
    '''Transform a a table in string form into a numpy array
    
    Parameters
    ----------
    string : string
    
    Returns
    -------
    numpy array
    '''
    stringIO = StringIO(string)
    return np.loadtxt(stringIO, **kargs)

def PL_signal_ratio(E, delta = 1000., exponent = -1.96):
    '''Ratio between the intensity at E and E+delta in a powerlaw
    
    Parameters:
    -----------
    E : float or array
    delta : float
    exponent :  float 
    '''  
    return ((E+float(delta))/E)**exponent

def order_of_magnitude(number):
    '''Order of magnitude of the given number
    
    Parameters
    ----------
    number : float
    
    Returns
    -------
    Float
    '''
    return math.floor(math.log10(number))

def bragg_scattering_angle(d, E0 = 100):
    '''
    Parameters
    ----------
    d : float
        interplanar distance in m
    E0 : float
        Incident energy in keV
        
    Returns
    -------
    float : Semiangle of scattering of the first order difracted beam. This is 
    two times the bragg angle. 
    '''
    
    gamma = 1 + E0 / 511.
    v_rel = np.sqrt(1-1/gamma**2)
    e_lambda = 2*np.pi/(2590e9*(gamma*v_rel)) # m
    print "Lambda = ", e_lambda
    
    return e_lambda / d

def effective_Z(Z_list, exponent = 2.94):
    '''Effective atomic number of a compound or mixture
    
    exponent = 2.94 for X-ray absorption
    
    Parameters
    ----------
    Z_list : list
        A list of tuples (f,Z) where f is the number of atoms of the element in 
        the molecule and Z its atomic number 
    
    Return
    ------
    float
    '''
    exponent = float(exponent)
    temp = 0
    total_e = 0
    for Z in Z_list:
        temp += Z[1]*Z[1]**exponent
        total_e += Z[0]*Z[1]
    print total_e
    return (temp/total_e)**(1/exponent)

def power_law_perc_area(E1,E2, r):
    a = E1
    b = E2
    return 100*((a**r*r-a**r)*(a/(a**r*r-a**r)-(b+a)/((b+a)**r*r-(b+a)**r)))/a

def rel_std_of_fraction(a,std_a,b,std_b,corr_factor = 1):
    rel_a = std_a/a
    rel_b = std_b/b
    return np.sqrt(rel_a**2 +  rel_b**2-2*rel_a*rel_b*corr_factor)

def ratio(edge_A, edge_B):
    a = edge_A.intensity.value
    std_a = edge_A.intensity.std
    b = edge_B.intensity.value
    std_b = edge_B.intensity.std
    ratio = a/b
    ratio_std = ratio * rel_std_of_fraction(a,std_a,b, std_b)
    print "Ratio %s/%s %1.3f +- %1.3f " % (edge_A.name, edge_B.name, a/b, 
    1.96*ratio_std )
    return ratio, ratio_std
