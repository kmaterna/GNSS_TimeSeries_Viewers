"""
Toolbox for operating on Timeseries objects.
Contains functions to map, filter, reduce, and process generic GPS time series
"""

import numpy as np
import datetime as dt
from scipy import signal
from . import lssq_model_errors, utilities, math_functions
from Tectonic_Utils.geodesy import insar_vector_functions


class Timeseries:
    # The classic timeseries internal object!
    def __init__(self, name, coords, dtarray, dN, dE, dU, Sn, Se, Su, EQtimes):
        self.name = name;
        self.coords = coords;
        self.dtarray = dtarray;  # 1d array of datetime objects
        self.dN = dN;  # 1d arrays in mm
        self.dE = dE;
        self.dU = dU;
        self.Sn = Sn;  # 1d arrays in mm
        self.Se = Se;
        self.Su = Su;
        self.EQtimes = EQtimes;

    # -------------------------------------------- #
    #              PREDICATES
    # -------------------------------------------- #

    def covers_date(self, include_time):
        if self.dtarray[0] < include_time < self.dtarray[-1]:
            return 1;
        else:
            return 0;

    def covers_date_range(self, include_time_start, include_time_end):
        if self.dtarray[0] < include_time_start and self.dtarray[-1] > include_time_end:
            return 1;
        else:
            return 0;

    # -------------------------------------------- #
    # PROCESSES THAT RETURN NEW TIME SERIES OBJECTS
    # -------------------------------------------- #

    def remove_outliers(self, outliers_def):
        medfilt_e = signal.medfilt(self.dE, 35);
        medfilt_n = signal.medfilt(self.dN, 35);
        medfilt_u = signal.medfilt(self.dU, 35);
        newdt, newdN, newdE, newdU, newSe, newSn, newSu = [], [], [], [], [], [], [];
        for i in range(len(medfilt_e)):
            if abs(self.dE[i] - medfilt_e[i]) < outliers_def and abs(self.dN[i] - medfilt_n[i]) < outliers_def and abs(
                    self.dU[i] - medfilt_u[i]) < outliers_def * 2:
                newdt.append(self.dtarray[i]);
                newdE.append(self.dE[i]);
                newdN.append(self.dN[i]);
                newdU.append(self.dU[i]);
                newSe.append(self.Se[i]);
                newSn.append(self.Sn[i]);
                newSu.append(self.Su[i]);
        newData = Timeseries(name=self.name, coords=self.coords, dtarray=newdt, dN=np.array(newdN), dE=np.array(newdE),
                             dU=np.array(newdU), Sn=newSn, Se=newSe, Su=newSu, EQtimes=self.EQtimes);
        return newData;

    def impose_time_limits(self, starttime, endtime):
        """
        :param starttime: datetime object
        :param endtime:  datetime object
        :return: a Timeseries object
        """
        newdtarray, newdN, newdE, newdU, newSe, newSn, newSu = [], [], [], [], [], [], [];
        for i in range(len(self.dN)):
            if starttime <= self.dtarray[i] <= endtime:
                newdtarray.append(self.dtarray[i]);
                newdE.append(self.dE[i]);
                newdN.append(self.dN[i]);
                newdU.append(self.dU[i]);
                newSe.append(self.Se[i]);
                newSn.append(self.Sn[i]);
                newSu.append(self.Su[i]);
        newData = Timeseries(name=self.name, coords=self.coords, dtarray=newdtarray, dN=np.array(newdN),
                             dE=np.array(newdE), dU=np.array(newdU), Sn=newSn, Se=newSe, Su=newSu,
                             EQtimes=self.EQtimes);
        return newData;

    def remove_nans(self):
        idxE, idxN, idxU = np.isnan(self.dE), np.isnan(self.dN), np.isnan(self.dU);
        temp_dates, temp_east, temp_north, temp_vert = [], [], [], [];
        temp_Sn, temp_Se, temp_Su = [], [], [];
        if (sum(idxN) + sum(idxE) + sum(idxU)) == 0:
            return self;
        else:  # if there are nans, please pull them out.
            for i in range(len(self.dtarray)):
                if idxE[i] == 0 and idxN[i] == 0 and idxU[i] == 0:
                    temp_dates.append(self.dtarray[i]);
                    temp_east.append(self.dE[i]);
                    temp_north.append(self.dN[i]);
                    temp_vert.append(self.dU[i]);
                    temp_Se.append(self.Se[i]);
                    temp_Sn.append(self.Sn[i]);
                    temp_Su.append(self.Su[i]);
            newData = Timeseries(name=self.name, coords=self.coords, dtarray=temp_dates, dN=np.array(temp_north),
                                 dE=np.array(temp_east), dU=np.array(temp_vert),
                                 Sn=temp_Sn, Se=temp_Se, Su=temp_Su, EQtimes=self.EQtimes);
        return newData;

    def remove_constant(self, east_offset=0, north_offset=0, vert_offset=0):
        """Subtract a constant number from each data array in a time series object

        :param east_offset: a scalar, in mm
        :param north_offset: a scalar, in mm
        :param vert_offset: a scalar, in mm
        """
        temp_east = np.array([x - east_offset for x in self.dE]);
        temp_north = np.array([x - north_offset for x in self.dN]);
        temp_vert = np.array([x - vert_offset for x in self.dU]);
        newData = Timeseries(name=self.name, coords=self.coords, dtarray=self.dtarray,
                             dN=np.array(temp_north), dE=np.array(temp_east), dU=np.array(temp_vert),
                             Sn=self.Sn, Se=self.Se, Su=self.Su, EQtimes=self.EQtimes);
        return newData;

    def embed_tsobject_with_eqdates(self, eq_obj):
        """
        :param eq_obj: a list of Offset objects to embed into the Timeseries metadata
        """
        eqdates = [x.evdt for x in eq_obj];
        newData = Timeseries(name=self.name, coords=self.coords, dtarray=self.dtarray, dN=self.dN,
                             dE=self.dE, dU=self.dU, Sn=self.Sn, Se=self.Se,
                             Su=self.Su, EQtimes=eqdates);
        return newData;

    def rotate_data(self, azimuth):  # should test to make sure this works the way I think it does.
        """
        :param azimuth: degrees, CW from north
        :return: a Timeseries object. ts.e is associated with the new azimuth; ts.e is associated with azimuth+90.
        """
        newE, newN = [], [];
        theta = insar_vector_functions.bearing_to_cartesian(azimuth);
        for i in range(len(self.dtarray)):
            new_position = insar_vector_functions.rotate_vector_by_angle(self.dE[i], self.dN[i], theta);
            newE.append(new_position[0]);
            newN.append(new_position[1]);
        rotated_ts = Timeseries(name=self.name, coords=self.coords, dtarray=self.dtarray,
                                dN=np.array(newN), dE=np.array(newE), dU=self.dU,
                                Sn=self.Sn, Se=self.Se, Su=self.Su, EQtimes=self.EQtimes);
        return rotated_ts;

    def detrend_data_by_value(self, east_params, north_params, vert_params):
        if sum(np.isnan(east_params)) > 0 or sum(np.isnan(north_params)) > 0 or sum(np.isnan(vert_params)) > 0:
            print("ERROR: Your input slope values contain nan!");
            return self;

        # Parameters Format: slope, a2(cos), a1(sin), s2, s1.
        east_detrended, north_detrended, vert_detrended = [], [], [];
        self.remove_nans();
        decyear = utilities.get_float_times(self.dtarray);

        east_model = math_functions.linear_annual_semiannual_function(decyear, east_params);
        north_model = math_functions.linear_annual_semiannual_function(decyear, north_params);
        vert_model = math_functions.linear_annual_semiannual_function(decyear, vert_params);

        for i in range(len(decyear)):
            east_detrended.append(self.dE[i] - (east_model[i]));
            north_detrended.append(self.dN[i] - (north_model[i]));
            vert_detrended.append(self.dU[i] - (vert_model[i]));
        east_detrended = [x - east_detrended[0] for x in east_detrended];
        north_detrended = [x - north_detrended[0] for x in north_detrended];
        vert_detrended = [x - vert_detrended[0] for x in vert_detrended];
        newData = Timeseries(name=self.name, coords=self.coords, dtarray=self.dtarray, dN=north_detrended,
                             dE=east_detrended, dU=vert_detrended, Sn=self.Sn, Se=self.Se, Su=self.Su,
                             EQtimes=self.EQtimes);
        return newData;

    def remove_seasonal_by_value(self, east_params, north_params, vert_params):
        """
        Least squares seasonal parameters. Remove seasonal components.
        Parameters Format: slope, a2(cos), a1(sin), s2, s1.
        """
        east_detrended, north_detrended, vert_detrended = [], [], [];
        self.remove_nans();
        decyear = utilities.get_float_times(self.dtarray);

        east_model = math_functions.annual_semiannual_only_function(decyear, east_params[1:]);
        north_model = math_functions.annual_semiannual_only_function(decyear, north_params[1:]);
        vert_model = math_functions.annual_semiannual_only_function(decyear, vert_params[1:]);

        for i in range(len(decyear)):
            east_detrended.append(self.dE[i] - (east_model[i]));
            north_detrended.append(self.dN[i] - (north_model[i]));
            vert_detrended.append(self.dU[i] - (vert_model[i]));
        newData = Timeseries(name=self.name, coords=self.coords, dtarray=self.dtarray, dN=north_detrended,
                             dE=east_detrended, dU=vert_detrended, Sn=self.Sn, Se=self.Se, Su=self.Su,
                             EQtimes=self.EQtimes);
        return newData;

    # -------------------------------------------- #
    # REDUCE TIME SERIES OBJECTS TO SCALARS OR VALUES
    # -------------------------------------------- #

    def get_slope(self, starttime=None, endtime=None, missing_fraction=0.6):
        """
        Model data with a best-fit y = mx + b.
        Returns six numbers: e_slope, n_slope, v_slope, e_std, n_std, v_std
        """

        # Defensive programming
        error_flag, starttime, endtime = basic_defensive_programming(self, starttime, endtime);
        if error_flag:
            print("Basic defensive programming failed. Returning nans for slopes");
            return [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan];

        # Cut to desired window, and remove nans
        self.remove_nans();
        self.impose_time_limits(starttime, endtime);

        # More defensive programming
        if len(self.dtarray) <= 2:
            print("ERROR: no time array for station %s. Returning Nan" % self.name);
            return [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan];
        time_duration = self.dtarray[-1] - self.dtarray[0];
        if time_duration.days < 270:
            print(
                "ERROR: using <<<1 year of data to estimate parameters for station %s. Returning Nan" % self.name);
            return [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan];
        if len(self.dE) < time_duration.days * missing_fraction:
            print(
                "ERROR: Most of the data is missing to estimate parameters for station %s. Returning Nan" % self.name);
            return [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan];

        # doing the inversion here, since it's only one line.
        decyear = utilities.get_float_times(self.dtarray);
        east_coef = np.polyfit(decyear, self.dE, 1);
        north_coef = np.polyfit(decyear, self.dN, 1);
        vert_coef = np.polyfit(decyear, self.dU, 1);
        east_slope, north_slope, vert_slope = east_coef[0], north_coef[0], vert_coef[0];

        # How bad is the fit to the line?
        east_trend = [east_coef[0] * x + east_coef[1] for x in decyear];
        east_detrended = [self.dE[i] - east_trend[i] for i in range(len(self.dE))];
        east_std = np.std(east_detrended);
        north_trend = [north_coef[0] * x + north_coef[1] for x in decyear];
        north_detrended = [self.dN[i] - north_trend[i] for i in range(len(self.dN))];
        north_std = np.std(north_detrended);
        vert_trend = [vert_coef[0] * x + vert_coef[1] for x in decyear];
        vert_detrended = [self.dU[i] - vert_trend[i] for i in range(len(self.dU))];
        vert_std = np.std(vert_detrended);

        return [east_slope, north_slope, vert_slope, east_std, north_std, vert_std];

    def get_slope_unc(self, starttime, endtime):
        """
        Calculate Allan Variance of Rates.
        slope is returned as params[0]
        """
        self.impose_time_limits(starttime, endtime);
        x = utilities.get_float_times(self.dtarray);
        params, covm = lssq_model_errors.AVR(x, self.dE, self.Se, verbose=0);
        Esigma = np.sqrt(covm[0][0]);
        params, covm = lssq_model_errors.AVR(x, self.dN, self.Sn, verbose=0);
        Nsigma = np.sqrt(covm[0][0]);
        params, covm = lssq_model_errors.AVR(x, self.dU, self.Su, verbose=0);
        Usigma = np.sqrt(covm[0][0]);
        return [Esigma, Nsigma, Usigma];

    def get_means(self, starttime=None, endtime=None):
        """
        Return average value of the time series between starttime and endtime
        """
        # Defensive programming
        error_flag, starttime, endtime = basic_defensive_programming(self, starttime, endtime);
        if error_flag:
            return [np.nan, np.nan, np.nan];
        self.remove_nans();  # Cut to desired window, and remove nans
        self.impose_time_limits(starttime, endtime);
        return [np.nanmean(self.dE), np.nanmean(self.dN), np.nanmean(self.dU)];

    def get_gap_fraction(self):
        """Compute the fraction of the time series that is not present. """
        starttime = self.dtarray[0];
        endtime = self.dtarray[-1];
        delta = endtime - starttime;
        total_possible_days = delta.days;
        days_present = len(self.dtarray);
        return 1 - (days_present / total_possible_days);

    def get_logfunction_params(self, eqtime):
        """
        y = B + Alog(1+t/tau), t is in decyear
        Useful for postseismic transients.
        """
        float_times = utilities.get_relative_times(self.dtarray, eqtime);  # in days
        e_params, ecov = math_functions.invert_log_function(float_times, self.dE);
        n_params, ecov = math_functions.invert_log_function(float_times, self.dN);
        u_params, ecov = math_functions.invert_log_function(float_times, self.dU);
        return [e_params, n_params, u_params];

    def get_values_at_date(self, selected_date, num_days=10):
        """ At a selected date, pull out the east, north, and up values at that date. """
        if selected_date in self.dtarray:
            idx = self.dtarray.index(selected_date);
            e_value = np.nanmean(self.dE[idx:idx + num_days]);
            n_value = np.nanmean(self.dN[idx:idx + num_days]);
            u_value = np.nanmean(self.dU[idx:idx + num_days]);
        else:
            print("Error: requested date %s not found in dtarray" % dt.datetime.strftime(selected_date, "%Y-%m-%d"));
            [e_value, n_value, u_value] = [np.nan, np.nan, np.nan];
        return e_value, n_value, u_value;

    def subsample_in_time(self, target_time, window_days=30):
        """
        Downsample TS: return position corresponding a given time by averaging over a month around target date.
        Almost the same as the function above, just with a little smarter window-handling for gaps.
        return E0, N0, U0
        """
        dE_start, dN_start, dU_start = [], [], [];
        for i in range(len(self.dtarray)):
            if abs((self.dtarray[i] - target_time).days) < window_days:
                dE_start.append(self.dE[i]);
                dN_start.append(self.dN[i]);
                dU_start.append(self.dU[i]);
        if len(dE_start) > 2:
            E0, N0, U0 = np.nanmean(dE_start), np.nanmean(dN_start), np.nanmean(dU_start);
        else:
            E0, N0, U0 = np.nan, np.nan, np.nan;
        return E0, N0, U0;

    def get_linear_annual_semiannual(self, starttime=None, endtime=None, critical_len=365):
        """
        The critical_len parameter allows us to switch this function for both GPS and GRACE time series in GPS format
        Model the data with a best-fit GPS = Acos(wt) + Bsin(wt) + Ccos(2wt) + Dsin(2wt) + E*t + F;
        """

        # Defensive programming
        error_flag, starttime, endtime = basic_defensive_programming(self, starttime, endtime);
        if error_flag:
            east_params = [np.nan, 0, 0, 0, 0];
            north_params = [np.nan, 0, 0, 0, 0];
            vert_params = [np.nan, 0, 0, 0, 0];
            return [east_params, north_params, vert_params];

        # Cut to desired window, and remove nans
        self.remove_nans();
        self.impose_time_limits(starttime, endtime);

        duration = self.dtarray[-1] - self.dtarray[0];
        if duration.days < critical_len:
            print(
                "ERROR: using less than 1 year of data to estimate params for station %s. Returning Nan" % self.name);
            east_params = [np.nan, 0, 0, 0, 0];
            north_params = [np.nan, 0, 0, 0, 0];
            up_params = [np.nan, 0, 0, 0, 0];
            return [east_params, north_params, up_params];

        decyear = utilities.get_float_times(self.dtarray);
        east_params_unordered = math_functions.invert_linear_annual_semiannual(decyear, self.dE);
        north_params_unordered = math_functions.invert_linear_annual_semiannual(decyear, self.dN);
        vert_params_unordered = math_functions.invert_linear_annual_semiannual(decyear, self.dU);

        # The definition for returning parameters:
        # slope, a2(cos), a1(sin), s2, s1.
        east_params = [east_params_unordered[4], east_params_unordered[0], east_params_unordered[1],
                       east_params_unordered[2], east_params_unordered[3]];
        north_params = [north_params_unordered[4], north_params_unordered[0], north_params_unordered[1],
                        north_params_unordered[2], north_params_unordered[3]];
        vert_params = [vert_params_unordered[4], vert_params_unordered[0], vert_params_unordered[1],
                       vert_params_unordered[2], vert_params_unordered[3]];

        return [east_params, north_params, vert_params];


# -------------------------------------------- #
#           DEFENSIVE PROGRAMMING
# -------------------------------------------- #

def basic_defensive_programming(Data0, starttime, endtime):
    """
    Check for all sorts of nasty things that disturb the calculation of slopes, etc.
    """
    error_flag = 0;

    if len(Data0.dtarray) == 0:
        print("Error: length of dtarray is 0 for station %s. " % Data0.name);
        error_flag = 1;
        return error_flag, starttime, endtime;

    if starttime is None:
        starttime = Data0.dtarray[0];
    if endtime is None:
        endtime = Data0.dtarray[-1];

    starttime_proper, endtime_proper = starttime, endtime;

    if starttime < Data0.dtarray[0]:
        starttime_proper = Data0.dtarray[0];
    if endtime > Data0.dtarray[-1]:
        endtime_proper = Data0.dtarray[-1];

    if endtime < Data0.dtarray[0]:
        print("Error: end time before start of array for station %s. Returning Nan" % Data0.name);
        error_flag = 1;
    if starttime > Data0.dtarray[-1]:
        print("Error: start time after end of array for station %s. Returning Nan" % Data0.name);
        error_flag = 1;

    return error_flag, starttime_proper, endtime_proper;


# -------------------------------------------- #
# FUNCTIONS THAT OPERATE ON TWO TIMESERIES OBJECTS
# -------------------------------------------- #

def pair_gps_model(gps_data: Timeseries, model_data: Timeseries):
    """
    Take two time series objects, and return two paired time series objects.
    It could be that GPS has days that model doesn't, or the other way around.
    """
    dtarray, dE_gps, dN_gps, dU_gps, Se_gps, Sn_gps, Su_gps = [], [], [], [], [], [], [];
    dE_model, dN_model, dU_model, Se_model, Sn_model, Su_model = [], [], [], [], [], [];
    gps_data = gps_data.remove_nans();
    model_data = model_data.remove_nans();
    for i in range(len(gps_data.dtarray)):
        if gps_data.dtarray[i] in model_data.dtarray:
            idx = model_data.dtarray.index(gps_data.dtarray[i]);  # where is this datetime object in the model array?
            dtarray.append(gps_data.dtarray[i]);
            dE_gps.append(gps_data.dE[i]);
            dN_gps.append(gps_data.dN[i]);
            dU_gps.append(gps_data.dU[i]);
            Se_gps.append(gps_data.Se[i]);
            Sn_gps.append(gps_data.Sn[i]);
            Su_gps.append(gps_data.Su[i]);
            dE_model.append(model_data.dE[idx]);
            dN_model.append(model_data.dN[idx]);
            dU_model.append(model_data.dU[idx]);
            Se_model.append(model_data.Se[idx]);
            Sn_model.append(model_data.Sn[idx]);
            Su_model.append(model_data.Su[idx]);
    paired_gps = Timeseries(name=gps_data.name, coords=gps_data.coords, dtarray=dtarray, dE=dE_gps, dN=dN_gps,
                            dU=dU_gps, Se=Se_gps, Sn=Sn_gps, Su=Su_gps, EQtimes=gps_data.EQtimes);
    paired_model = Timeseries(name=model_data.name, coords=model_data.coords, dtarray=dtarray, dE=dE_model, dN=dN_model,
                              dU=dU_model, Se=Se_model, Sn=Sn_model, Su=Su_model, EQtimes=model_data.EQtimes);
    return [paired_gps, paired_model];


def pair_gps_model_keeping_gps(gps_data: Timeseries, model_data: Timeseries):
    """
    Take two time series objects, and return two time series objects.
    Keep all data from the first one.
    Generate a model_data with length that matches the GPS.
    """
    dtarray, dE_model, dN_model, dU_model, Se_model, Sn_model, Su_model = [], [], [], [], [], [], [];
    gps_data = gps_data.remove_nans();
    model_data = model_data.remove_nans();
    for i in range(len(gps_data.dtarray)):
        if gps_data.dtarray[i] in model_data.dtarray:
            idx = model_data.dtarray.index(gps_data.dtarray[i]);  # where is this datetime object in the model array?
            dtarray.append(gps_data.dtarray[i]);
            dE_model.append(model_data.dE[idx]);
            dN_model.append(model_data.dN[idx]);
            dU_model.append(model_data.dU[idx]);
            Se_model.append(model_data.Se[idx]);
            Sn_model.append(model_data.Sn[idx]);
            Su_model.append(model_data.Su[idx]);
        else:
            dtarray.append(gps_data.dtarray[i]);  # if we can't find it, then we put filler model.
            dE_model.append(0);
            dN_model.append(0);
            dU_model.append(0);
            Se_model.append(0);
            Sn_model.append(0);
            Su_model.append(0);
    paired_model = Timeseries(name=model_data.name, coords=model_data.coords, dtarray=dtarray, dE=dE_model, dN=dN_model,
                              dU=dU_model, Se=Se_model, Sn=Sn_model, Su=Su_model, EQtimes=model_data.EQtimes);
    return [gps_data, paired_model];


def get_referenced_data(roving_station_data: Timeseries, base_station_data: Timeseries):
    """
    Take a time series object and remove motion of a base station (another time series object)
    If there's a starttime, then we will solve for a best-fitting model offset at starttime.
    Used when subtracting models
    """
    dtarray, dE_gps, dN_gps, dU_gps, Se_gps, Sn_gps, Su_gps = [], [], [], [], [], [], [];
    roving_station_data = roving_station_data.remove_nans();
    for i in range(len(roving_station_data.dtarray)):
        if roving_station_data.dtarray[i] in base_station_data.dtarray:
            idx = base_station_data.dtarray.index(
                roving_station_data.dtarray[i]);  # where is this datetime object in the model array?
            dtarray.append(roving_station_data.dtarray[i]);
            dE_gps.append(roving_station_data.dE[i] - base_station_data.dE[idx]);
            dN_gps.append(roving_station_data.dN[i] - base_station_data.dN[idx]);
            dU_gps.append(roving_station_data.dU[i] - base_station_data.dU[idx]);
            Se_gps.append(roving_station_data.Se[i]);
            Sn_gps.append(roving_station_data.Sn[i]);
            Su_gps.append(roving_station_data.Su[i]);
    gps_relative = Timeseries(name=roving_station_data.name, coords=roving_station_data.coords, dtarray=dtarray,
                              dE=np.array(dE_gps), dN=np.array(dN_gps), dU=np.array(dU_gps), Se=np.array(Se_gps),
                              Sn=np.array(Sn_gps), Su=np.array(Su_gps), EQtimes=roving_station_data.EQtimes);
    return gps_relative;

# -------------------------------------------- #
# FOR REVERSE COMPATIBILITY (MAY BE DEPRECATED)
# -------------------------------------------- #

def remove_outliers(Data0: Timeseries, outliers_def: float):
    return Data0.remove_outliers(outliers_def);

def impose_time_limits(Data0: Timeseries, starttime: dt.datetime, endtime: dt.datetime):
    return Data0.impose_time_limits(starttime, endtime);

def remove_nans(Data0: Timeseries):
    return Data0.remove_nans();

def remove_constant(Data0: Timeseries, east_offset=0, north_offset=0, vert_offset=0):
    return Data0.remove_constant(east_offset, north_offset, vert_offset);

def embed_tsobject_with_eqdates(Data0: Timeseries, eq_obj):
    return Data0.embed_tsobject_with_eqdates(eq_obj);

def detrend_data_by_value(Data0: Timeseries, east_params, north_params, vert_params):
    return Data0.detrend_data_by_value(east_params, north_params, vert_params);

def remove_seasonal_by_value(Data0: Timeseries, east_params, north_params, vert_params):
    return Data0.remove_seasonal_by_value(east_params, north_params, vert_params);

def get_slope(Data0: Timeseries, starttime=None, endtime=None, missing_fraction=0.6):
    return Data0.get_slope(starttime, endtime, missing_fraction);

def get_slope_unc(dataObj: Timeseries, starttime, endtime):
    return dataObj.get_slope_unc(starttime, endtime);

def get_linear_annual_semiannual(Data0: Timeseries, starttime=None, endtime=None, critical_len=365):
    return Data0.get_linear_annual_semiannual(starttime, endtime, critical_len);

def get_means(Data0: Timeseries, starttime=None, endtime=None):
    return Data0.get_means(starttime, endtime);

def get_logfunction_params(Data0: Timeseries, eqtime):
    return Data0.get_logfunction_params(eqtime);

def get_values_at_date(Data0: Timeseries, selected_date, num_days=10):
    return Data0.get_values_at_date(selected_date, num_days);
