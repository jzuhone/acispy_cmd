#!/usr/bin/env python

import matplotlib
import matplotlib.pyplot as plt
import argparse
import acispy
from acispy.utils import state_labels, mylog
from Chandra.Time import date2secs, secs2date
matplotlib.use("Qt5Agg")


def main():
    
    parser = argparse.ArgumentParser(description='Plot one or more MSIDs or states from the ACIS 10-day tracelog files.')
    parser.add_argument("fields", type=str, help='The MSIDs and states to plot, comma-separated')
    parser.add_argument("--days", type=int, default=10, help='The number of days before the end of the log to plot. Default: 10')
    parser.add_argument("--one-panel", action='store_true',
                        help="Whether to make a multi-panel plot or a single-panel plot. The latter is only valid if the quantities have the same units.")
    args = parser.parse_args()
    
    states = []
    msids = []
    
    for p in args.fields.split(','):
        if p in state_labels:
            states.append(p)
        else:
            msids.append(p)
    
    fields = [("msids", m) for m in msids] + [("states", s) for s in states]
    
    ds = acispy.TenDayTracelogData()
    dates = ds["1dpamzt"].dates
    
    datestop = dates[-1]
    if args.days > 10:
        mylog.warning("Cannot plot more than 10 days from the 10-day tracelog. Plotting data from the full tracelog.")
    days = min(10, args.days)
    secs = days*24*3600.0
    datestart = secs2date(date2secs(datestop)-secs)
    
    if args.one_panel or len(fields) == 1:
        cp = acispy.DatePlot(ds, fields)
    else:
        cp = acispy.MultiDatePlot(ds, fields)
    cp.set_xlim(datestart, datestop)
    
    plt.show()


if __name__ == "__main__":
    main()