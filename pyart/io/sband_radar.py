"""
pyart.io.sband_radar
======================


"""

import struct
from datetime import datetime, timedelta

import numpy as np


class SbandRadarFile(object):
    """
    Class for accessing data in a S band file.

    Parameters
    ----------
    filename : str
        Filename of S band file to read.

    Attributes
    ----------
    radial_records : list
        Radial (1 or 31) messages in the file.
    nscans : int
        Number of scans in the file.
    scan_msgs : list of arrays
        Each element specifies the indices of the message in the
        radial_records attribute which belong to a given scan.
    volume_header : dict
        Volume header.
    vcp : dict
        VCP information dictionary.
    _records : list
        A list of all records (message) in the file.
    _fh : file-like
        File like object from which data is read.

    """
    def __init__(self, filename):
        """ initalize the object. """
        # read in the volume header and compression_record
        if hasattr(filename, 'read'):
            fh = filename
        else:
            fh = open(filename, 'rb')

        buf = fh.read()

        self._fh = fh

        # read the records from the buffer
        self._records = []
        buf_length = len(buf)
        pos = 0
        while pos < buf_length:
            pos, dic = _get_record_from_buf(buf, pos)
            self._records.append(dic)

        # pull out radial records which contain the moment data.
        self.radial_records = [r for r in self._records]

        elev_nums = np.array([m['msg_header']['elevation_number']
                              for m in self.radial_records])
        self.scan_msgs = [np.where(elev_nums == i + 1)[0]
                          for i in range(elev_nums.max())]
        self.nscans = len(self.scan_msgs)

        # pull out the vcp record
        self.vcp = None

        return

    def close(self):
        """ Close the file. """
        self._fh.close()
        
    def scan_info(self, scans=None):
        """
        Return a list of dictionaries with scan information.

        Parameters
        ----------
        scans : list ot None
            Scans (0 based) for which ray (radial) azimuth angles will be
            retrieved.  None (the default) will return the angles for all
            scans in the volume.

        Returns
        -------
        scan_info : list, optional
            A list of the scan performed with a dictionary with keys
            'moments', 'ngates', 'nrays', 'first_gate' and 'gate_spacing'
            for each scan.  The 'moments', 'ngates', 'first_gate', and
            'gate_spacing' keys are lists of the NEXRAD moments and gate
            information for that moment collected during the specific scan.
            The 'nrays' key provides the number of radials collected in the
            given scan.

        """
        info = []
        if scans is None:
            scans = range(self.nscans)
        for scan in scans:
            nrays = self.get_nrays(scan)

            msg_number = self.scan_msgs[scan][0]
            msg = self.radial_records[msg_number]

            nexrad_moments = ['REF', 'VEL', 'SW']
            moments = [f for f in nexrad_moments if f in msg]
            ngates = [msg[f]['ngates'] for f in moments]
            gate_spacing = [msg[f]['gate_spacing'] for f in moments]
            first_gate = [msg[f]['first_gate'] for f in moments]

            info.append({
                'nrays': nrays,
                'ngates': ngates,
                'gate_spacing': gate_spacing,
                'first_gate': first_gate,
                'moments': moments})

        return info

    def get_vcp_pattern(self):
        """
        Return the numerical volume coverage pattern (VCP) or None if unknown.
        """
        if self.vcp is None:
            return None
        else:
            return self.vcp['msg5_header']['pattern_number']

    def get_nrays(self, scan):
        """
        Return the number of rays in a given scan.

        Parameters
        ----------
        scan : int
            Scan of interest (0 based)

        Returns
        -------
        nrays : int
            Number of rays (radials) in the scan.

        """
        return len(self.scan_msgs[scan])

    def get_range(self, scan_num, moment):
        """
        Return an array of gate ranges for a given scan and moment.

        Parameters
        ----------
        scan_num : int
            Scan number (0 based).
        moment : 'REF', 'VEL', 'SW', 'ZDR', 'PHI', or 'RHO'
            Moment of interest.

        Returns
        -------
        range : ndarray
            Range in meters from the antenna to the center of gate (bin).

        """
        dic = self.radial_records[self.scan_msgs[scan_num][0]][moment]
        ngates = dic['ngates']
        first_gate = dic['first_gate']
        gate_spacing = dic['gate_spacing']
        return np.arange(ngates) * gate_spacing + first_gate

    # helper functions for looping over scans
    def _msg_nums(self, scans):
        """ Find the all message number for a list of scans. """

        return np.concatenate([self.scan_msgs[i] for i in scans])

    def _radial_array(self, scans, key):
        """
        Return an array of radial header elements for all rays in scans.
        """
        msg_nums = self._msg_nums(scans)

        temp = [self.radial_records[i]['msg_header'][key] for i in msg_nums]
        return np.array(temp)

    def _radial_sub_array(self, scans, key):
        """
        Return an array of RAD or msg_header elements for all rays in scans.
        """
        msg_nums = self._msg_nums(scans)

        tmp = [self.radial_records[i]['msg_header'][key] for i in msg_nums]
        
        return np.array(tmp)

    def get_times(self, scans=None):
        """
        Retrieve the times at which the rays were collected.

        Parameters
        ----------
        scans : list or None
            Scans (0-based) to retrieve ray (radial) collection times from.
            None (the default) will return the times for all scans in the
            volume.

        Returns
        -------
        time_start : Datetime
            Initial time.
        time : ndarray
            Offset in seconds from the initial time at which the rays
            in the requested scans were collected.

        """
        if scans is None:
            scans = range(self.nscans)
        days = self._radial_array(scans, 'collect_date')
        secs = self._radial_array(scans, 'collect_ms') / 1000.
        offset = timedelta(days=int(days[0]) - 1, seconds=int(secs[0]))
        time_start = datetime(1970, 1, 1) + offset
        time = secs - int(secs[0]) + (days - days[0]) * 86400
        return time_start, time

    def get_azimuth_angles(self, scans=None):
        """
        Retrieve the azimuth angles of all rays in the requested scans.

        Parameters
        ----------
        scans : list ot None
            Scans (0 based) for which ray (radial) azimuth angles will be
            retrieved.  None (the default) will return the angles for all
            scans in the volume.

        Returns
        -------
        angles : ndarray
            Azimuth angles in degress for all rays in the requested scans.

        """
        scale = 180 / (4096 * 8.)
        
        if scans is None:
            scans = range(self.nscans)
        else:
            raise ValueError("scans error!")

        return self._radial_array(scans, 'azimuth_angle') * scale

    def get_elevation_angles(self, scans=None):
        """
        Retrieve the elevation angles of all rays in the requested scans.

        Parameters
        ----------
        scans : list or None
            Scans (0 based) for which ray (radial) azimuth angles will be
            retrieved. None (the default) will return the angles for
            all scans in the volume.

        Returns
        -------
        angles : ndarray
            Elevation angles in degress for all rays in the requested scans.

        """
        scale = 180 / (4096 * 8.)
        
        if scans is None:
            scans = range(self.nscans)
        else:
            raise ValueError("scans error!")

        return self._radial_array(scans, 'elevation_angle') * scale

    def get_target_angles(self, scans=None):
        """
        Retrieve the target elevation angle of the requested scans.

        Parameters
        ----------
        scans : list or None
            Scans (0 based) for which the target elevation angles will be
            retrieved. None (the default) will return the angles for all
            scans in the volume.

        Returns
        -------
        angles : ndarray
            Target elevation angles in degress for the requested scans.

        """
        if scans is None:
            scans = range(self.nscans)
        else:
            raise ValueError("scans error!")        
        
        scale = 180 / (4096 * 8.)
        msgs = [self.radial_records[self.scan_msgs[i][0]] for i in scans]
        return np.round(np.array(
            [m['msg_header']['elevation_angle'] * scale for m in msgs],
            dtype='float32'), 1)

    def get_nyquist_vel(self, scans=None):
        """
        Retrieve the Nyquist velocities of the requested scans.

        Parameters
        ----------
        scans : list or None
            Scans (0 based) for which the Nyquist velocities will be
            retrieved. None (the default) will return the velocities for all
            scans in the volume.

        Returns
        -------
        velocities : ndarray
            Nyquist velocities (in m/s) for the requested scans.

        """
        if scans is None:
            scans = range(self.nscans)
        return self._radial_sub_array(scans, 'nyquist_vel') * 0.01

    def get_unambigous_range(self, scans=None):
        """
        Retrieve the unambiguous range of the requested scans.

        Parameters
        ----------
        scans : list or None
            Scans (0 based) for which the unambiguous range will be retrieved.
            None (the default) will return the range for all scans in the
            volume.

        Returns
        -------
        unambiguous_range : ndarray
            Unambiguous range (in meters) for the requested scans.

        """
        if scans is None:
            scans = range(self.nscans)
        # unambiguous range is stored in tenths of km, x100 for meters
        return self._radial_sub_array(scans, 'unambig_range') / 10.

    def get_data(self, moment, max_ngates, scans=None, raw_data=False):
        """
        Retrieve moment data for a given set of scans.

        Masked points indicate that the data was not collected, below
        threshold or is range folded.

        Parameters
        ----------
        moment : 'REF', 'VEL', 'SW', 'ZDR', 'PHI', or 'RHO'
            Moment for which to to retrieve data.
        max_ngates : int
            Maximum number of gates (bins) in any ray.
            requested.
        raw_data : bool
            True to return the raw data, False to perform masking as well as
            applying the appropiate scale and offset to the data.  When
            raw_data is True values of 1 in the data likely indicate that
            the gate was not present in the sweep, in some cases in will
            indicate range folded data.
        scans : list or None.
            Scans to retrieve data from (0 based).  None (the default) will
            get the data for all scans in the volume.

        Returns
        -------
        data : ndarray

        """
        if scans is None:
            scans = range(self.nscans)

        # determine the number of rays
        msg_nums = self._msg_nums(scans)
        nrays = len(msg_nums)

        # extract the data
        data = np.ones((nrays, max_ngates), dtype='u1')
            
        for i, msg_num in enumerate(msg_nums):
            msg = self.radial_records[msg_num]
            if moment not in msg.keys():
                continue
            ngates = msg[moment]['ngates']
            data[i, :ngates] = msg[moment]['data']
               
        # return raw data if requested
        if raw_data:
            return data

        # mask, scan and offset, assume that the offset and scale
        # are the same in all scans/gates
        for scan in scans:  # find a scan which contains the moment
            msg_num = self.scan_msgs[scan][0]
            msg = self.radial_records[msg_num]
            if moment in msg.keys():
                offset = np.float32(msg[moment]['offset'])
                scale = np.float32(msg[moment]['scale'])

                mask = data <= 1
                
                scaled_data = (data - offset) / scale
                
                return np.ma.array(scaled_data, mask=mask)
        # moment is not present in any scan, mask all values
        return np.ma.masked_less_equal(data, 1)


def _unpack_from_buf(buf, pos, structure):
    """ Unpack a structure from a buffer. """
    size = _structure_size(structure)
    return _unpack_structure(buf[pos:pos + size], structure)

def _get_record_from_buf(buf, pos):
    """ Retrieve and unpack a NEXRAD record from a buffer. """
    dic = {'header': _unpack_from_buf(buf, pos, MSG_HEADER)}

    new_pos = _get_msg1_from_buf(buf, pos, dic)

    return new_pos, dic

def _get_msg1_from_buf(buf, pos, dic):
    """ Retrieve and unpack a MSG1 record from a buffer. """
    msg_header_size = _structure_size(MSG_HEADER)
    msg1_header = _unpack_from_buf(buf, pos + msg_header_size, MSG_1)
    dic['msg_header'] = msg1_header

    sur_nbins = int(msg1_header['sur_nbins'])
    doppler_nbins = int(msg1_header['doppler_nbins'])

    sur_step = int(msg1_header['sur_range_step'])
    doppler_step = int(msg1_header['doppler_range_step'])

    sur_first = int(msg1_header['sur_range_first'])
    doppler_first = int(msg1_header['doppler_range_first'])
    
    if doppler_first > 2**15:
        doppler_first = doppler_first - 2**16
        
    if msg1_header['sur_pointer']:
        offset = pos + msg_header_size + msg1_header['sur_pointer']     
        data = np.frombuffer(buf[offset:offset+sur_nbins], '>u1')
        dic['REF'] = {
            'ngates': sur_nbins,
            'gate_spacing': sur_step,
            'first_gate': sur_first,
            'data': data,
            'scale': 2.,
            'offset': 66.,
        }
    if msg1_header['vel_pointer']:
        offset = pos + msg_header_size + msg1_header['vel_pointer']
        data = np.frombuffer(buf[offset:offset+doppler_nbins], '>u1')

        dic['VEL'] = {
            'ngates': doppler_nbins,
            'gate_spacing': doppler_step,
            'first_gate': doppler_first,
            'data': data,
            'scale': 2.,
            'offset': 129.0,
        }
        if msg1_header['doppler_resolution'] == 4:
            # 1 m/s resolution velocity, offset remains 129.
            dic['VEL']['scale'] = 1.
    if msg1_header['width_pointer']:
        offset = pos + msg_header_size + msg1_header['width_pointer']
        data = np.frombuffer(buf[offset:offset+doppler_nbins], '>u1')
        dic['SW'] = {
            'ngates': doppler_nbins,
            'gate_spacing': doppler_step,
            'first_gate': doppler_first,
            'data': data,
            'scale': 2.,
            'offset': 129.0,
        }
    return pos + RECORD_SIZE

def _unpack_from_buf(buf, pos, structure):
    """ Unpack a structure from a buffer. """
    size = _structure_size(structure)
    return _unpack_structure(buf[pos:pos + size], structure)

def _structure_size(structure):
    """ Find the size of a structure in bytes. """
    return struct.calcsize("=" + "".join([i[1] for i in structure]))

def _unpack_structure(string, structure):
    """Unpack a structure from a string
    """
    fmt = "=" + "".join([i[1] for i in structure])
    lst = struct.unpack(fmt, string)

    return dict(zip([i[0] for i in structure], lst))



# NEXRAD Level II file structures and sizes
# The deails on these structures are documented in:
# "Interface Control Document for the Achive II/User" RPG Build 12.0
# Document Number 2620010E
# and
# "Interface Control Document for the RDA/RPG" Open Build 13.0
# Document Number 2620002M
# Tables and page number refer to those in the second document unless
# otherwise noted.
RECORD_SIZE = 2432

# format of structure elements
# section 3.2.1, page 3-2
CODE1 = 'B'
CODE2 = 'H'
INT1 = 'B'
INT2 = 'H'
INT4 = 'I'
REAL4 = 'f'
REAL8 = 'd'
SINT1 = 'b'
SINT2 = 'h'
SINT4 = 'i'

MSG_HEADER = (    
    ('reserved0', '14s'),
    ("style", "H"),
    ("reserved1", "12s"),)

MSG_1 = (
    ('collect_ms', 'I'),
    ('collect_date', 'H'),    
    ('unambig_range', 'H'),
    ('azimuth_angle', 'H'),
    ("azimuth_number", "H"),
    ("radial_status", "H"),
    ("elevation_angle", "H"),
    ("elevation_number", "H"),
    ("sur_range_first", "H"),
    ("doppler_range_first", "H"),
    ("sur_range_step", "H"),
    ("doppler_range_step", "H"),
    ("sur_nbins", "H"),
    ("doppler_nbins", "H"),
    ("cut_sector_num", "H"),
    ("calib_const", "I"),
    ("sur_pointer", "H"),
    ("vel_pointer", "H"),
    ("width_pointer", "H"),
    ("doppler_resolution", "H"),
    ("vcp", "H"),
    ("reserved2", "8B"),
    ("velocity_back_pointer", "H"),
    ("spectrum_back_pointer", "H"),
    ("velocity_back_resolution", "H"),
    ("nyquist_vel", "H"),
    ("reserved3", "38B"),
)
