# -*- coding: utf-8 -*-
# Copyright 2007-2016 The HyperSpy developers
#
# This file is part of  HyperSpy.
#
#  HyperSpy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
#  HyperSpy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with  HyperSpy.  If not, see <http://www.gnu.org/licenses/>.


from hyperspy._signals.complex_signal import ComplexSignal


class ComplexSignal1D(ComplexSignal):
    """BaseSignal subclass for complex 1-dimensional data."""

    _record_by = 'spectrum'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.axes_manager.set_signal_dimension(1)
        self.metadata.Signal.binned = False

    def to_signal2D(self):
        """Returns the one dimensional signal as a two dimensional signal.

        See Also
        --------
        as_signal2D : a method for the same purpose with more options.
        signals.Signal1D.to_signal2D : performs the inverse operation on images.

        Raises
        ------
        DataDimensionError: when data.ndim < 2

        """
        if self.data.ndim < 2:
            raise DataDimensionError(
                "A Signal dimension must be >= 2 to be converted to Signal2D")
        im = self.rollaxis(-1 + 3j, 0 + 3j)
        im.metadata.Signal.record_by = "image"
        im._assign_subclass()
        return im
