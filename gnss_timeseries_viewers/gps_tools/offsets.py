"""
Toolbox that operates on Timeseries objects to deal with antenna offsets and earthquake offsets.
"""
from . import vel_functions
from .gps_ts_functions import Timeseries
import numpy as np
import datetime as dt


class Offset:
    # Defining the offset as a class
    def __init__(self, evdt, e_offset=0, n_offset=0, u_offset=0):
        self.evdt = evdt  # datetime object, required
        self.e_offset = e_offset  # in mm.  Each field is a single value.
        self.n_offset = n_offset  # in mm
        self.u_offset = u_offset  # in mm

    def __str__(self):
        return f'{dt.datetime.strftime(self.evdt, "%Y-%m-%d")}, {np.round(self.e_offset, 5)} mmE, ' \
               f'{np.round(self.n_offset, 5)} mmN, {np.round(self.u_offset, 5)} mmU.'


def remove_offsets(Data0: Timeseries, offsets_list: list, verbose=False):
    """
    :param Data0: timeseries object
    :param offsets_list: list of Offset objects
    :param verbose: boolean
    :returns: a timeseries object
    """
    if len(offsets_list) == 0:
        return Data0
    newN, newE, newU = [], [], []

    # Removing offsets
    for i in range(len(Data0.dtarray)):
        # For each day.
        tempE, tempN, tempU = Data0.dE[i], Data0.dN[i], Data0.dU[i]
        for item in offsets_list:
            if verbose:
                print("removing %f mm from east at %s" % (item.e_offsets, item.evdt))
            if Data0.dtarray[i] == item.evdt:  # removing the date of the offset directly (can be messed up)
                tempE, tempN, tempU = np.nan, np.nan, np.nan
            if Data0.dtarray[i] > item.evdt:
                tempE = tempE - item.e_offset
                tempN = tempN - item.n_offset
                tempU = tempU - item.u_offset
        newE.append(tempE)
        newN.append(tempN)
        newU.append(tempU)

    newData = Timeseries(name=Data0.name, coords=Data0.coords, dtarray=Data0.dtarray, dN=newN, dE=newE, dU=newU,
                         Sn=Data0.Sn, Se=Data0.Se, Su=Data0.Su, EQtimes=Data0.EQtimes, Offsettimes=Data0.Offsettimes)
    return newData


def fit_single_offset(dtarray, data, interval: list, offset_num_days: int):
    """
    Solve for an offset at a given time in one component of data, like east
    Offset can be calculated at a day or an interval (day is just repeated twice.)

    :param dtarray: 1d array of datetimes
    :param data: 1d array of floats
    :param interval: [dt, dt] to show where the offset exists
    :param offset_num_days: int, size of the averaging window where pre/post event position will be computed
    """
    before_indeces, after_indeces = [], []

    # Find the indeces of nearby days
    for i in range(len(dtarray)):
        deltat_start = dtarray[i] - interval[0]  # the beginning of the interval
        deltat_end = dtarray[i] - interval[1]  # the end of the interval
        if -offset_num_days <= deltat_start.days <= 0:
            before_indeces.append(i)
        if 0 <= deltat_end.days <= offset_num_days:
            after_indeces.append(i)

    # Identify the value of the offset.
    if before_indeces == [] or after_indeces == [] or len(before_indeces) == 1 or len(after_indeces) == 1:
        offset = 0
        print("Warning: no data before or after offset at %s. Returning offset=0" % (
            dt.datetime.strftime(interval[0], "%Y-%m-%d")))
    else:
        before_mean = np.nanmean([data[x] for x in before_indeces])
        after_mean = np.nanmean([data[x] for x in after_indeces])
        offset = after_mean - before_mean
        if offset == np.nan:
            print("Warning: np.nan offset found. Returning 0")
            offset = 0
    return offset


def clean_expected_interval_list(offset_time_intervals: list, num_days):
    """
    Defensive programming to warn the user if multiple earthquakes happened in the same solving window,
    which might result in an offset being removed twice.

    :param offset_time_intervals: list of datetimes, or list of intervals
    :param num_days: int, number of days in the offset solving window
    :return: list of intervals
    """
    full_interval_list = []
    for item in offset_time_intervals:
        if isinstance(item, dt.datetime):  # build an interval from a single day.
            full_interval_list.append([item, item])  # build an interval from a single day.
        else:
            full_interval_list.append(item)  # use interval provided
    if len(full_interval_list) == 0 or len(full_interval_list) == 1:
        return full_interval_list
    inter_event_time = [full_interval_list[i+1][0] - full_interval_list[i][0] for i in range(len(full_interval_list)-1)]
    for i, x in enumerate(inter_event_time):
        if x.days < num_days / 2:
            print("WARNING: You may be solving for two offsets in the same solving window: %s and %s " %
                  (dt.datetime.strftime(full_interval_list[i][0], "%Y-%m-%d"),
                   dt.datetime.strftime(full_interval_list[i+1][0], "%Y-%m-%d")))
            print("Something may get messed up.")
    return full_interval_list


def solve_for_offsets(ts_object: Timeseries, offset_time_intervals: list, num_days=10):
    """
    Solve for all E/N/U offsets at given times. Necessary for UNR data.

    :param ts_object: timeseries object
    :param offset_time_intervals: list of individual datetimes, or list of [start, end] intervals,
     each one associated with an offset or earthquake
    :param num_days: int averaging window, default 10 days
    :returns: list of Offset objects
    """
    print("Solving empirically for offsets at ", offset_time_intervals)
    full_interval_list = clean_expected_interval_list(offset_time_intervals, num_days)

    Offset_obj = []
    for interval in full_interval_list:
        e_offset = fit_single_offset(ts_object.dtarray, ts_object.dE, [interval[0], interval[1]], num_days)
        n_offset = fit_single_offset(ts_object.dtarray, ts_object.dN, [interval[0], interval[1]], num_days)
        u_offset = fit_single_offset(ts_object.dtarray, ts_object.dU, [interval[0], interval[1]], num_days)
        newobj = Offset(evdt=interval[0], e_offset=e_offset, n_offset=n_offset, u_offset=u_offset)
        Offset_obj.append(newobj)
    return Offset_obj


def filter_offset_list_to_date(offset_list, date_of_interest):
    """Filter a list of possible offsets to only the offset on a particular day of interest."""
    for item in offset_list:
        if item.evdt == date_of_interest:
            return item
    return None


def table_offset_to_velfield(ts_obj_list, offset_obj_list, target_date):
    """
    Turn a list of offset_objects and ts_objects into a pseudo-vel object for plotting and writing.
    Querying the tables for offsets.

    :param ts_obj_list: list of timeseries objects
    :param offset_obj_list: list of list of Offset objects, one for each timeseries object
    :param target_date: datetime object
    :returns: list of StationVels
    """
    offsetpts = []
    for i in range(len(offset_obj_list)):
        offseti = filter_offset_list_to_date(offset_obj_list[i], target_date)
        tsi = ts_obj_list[i]
        if offseti is not None:
            offsetpts.append(package_offset_as_StationVel(tsi, offseti))
    print("Found %d look-up-table offsets, %s" % (len(offsetpts), dt.datetime.strftime(target_date, "%Y-%m-%d")))
    return offsetpts


def manual_offset_to_velfield(ts_obj_list, first_epoch, last_epoch, num_days=10):
    """
    Turn a list of ts_objects into an interval offset, expressed as pseudo-vel object for plotting and writing.
    Solving for timeseries offset between the start and last days.

    :param ts_obj_list: list of timeseries objects
    :param first_epoch: datetime object
    :param last_epoch: datetime object
    :param num_days: averaging window, default to 7 days
    :returns: list of StationVels
    """
    offsetpts = []
    for tsi in ts_obj_list:
        new_offset = solve_for_offsets(tsi, [[first_epoch, last_epoch]], num_days=num_days)[0]
        offsetpts.append(package_offset_as_StationVel(tsi, new_offset))
    print("Solved %d offsets around %s" % (len(offsetpts), dt.datetime.strftime(first_epoch, "%Y-%m-%d")))
    return offsetpts


def package_offset_as_StationVel(ts_object: Timeseries, offset: Offset):
    """
    :param ts_object: a timeseries object
    :param offset: an offset object
    :return: a StationVel
    """
    newobj = vel_functions.Station_Vel(name=ts_object.name, nlat=ts_object.coords[1], elon=ts_object.coords[0],
                                       n=offset.n_offset, e=offset.e_offset, u=offset.u_offset, sn=0, se=0, su=0,
                                       first_epoch='', last_epoch='')
    return newobj


def print_offset_object(Offset_obj, metadata=''):
    for item in Offset_obj:
        print(metadata, item)
    return
