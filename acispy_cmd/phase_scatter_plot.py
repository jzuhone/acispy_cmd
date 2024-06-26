#!/usr/bin/env python

import matplotlib
import matplotlib.pyplot as plt
import argparse
import acispy
from acispy.utils import state_labels, mylog
matplotlib.use("Qt5Agg")


def main():
    
    parser = argparse.ArgumentParser(description='Make a phase scatter plot of one MSID or state versus another within a certain time frame.')
    parser.add_argument("tstart", type=str, help='The start time in YYYY:DOY:HH:MM:SS format')
    parser.add_argument("tstop", type=str, help='The stop time in YYYY:DOY:HH:MM:SS format')
    parser.add_argument("x_field", type=str, help='The MSID or state to plot on the x-axis')
    parser.add_argument("y_field", type=str, help='The MSID or state to plot on the y-axis')
    parser.add_argument("--c_field", type=str, help='The MSID or state to plot using colors')
    parser.add_argument("--cmap", type=str, help='The colormap to use if plotting colors')
    parser.add_argument("--maude", action="store_true", help="Use MAUDE to get telemetry data.")
    args = parser.parse_args()
    
    msids = []
    
    if args.x_field in state_labels:
        x_field = ("states", args.x_field)
    else:
        msids.append(args.x_field)
        x_field = ("msids", args.x_field)
    
    if args.y_field in state_labels:
        y_field = ("states", args.y_field)
    else:
        msids.append(args.y_field)
        y_field = ("msids", args.y_field)
    
    if args.c_field is not None:
        if args.c_field in state_labels:
            c_field = ("states", args.c_field)
        else:
            msids.append(args.c_field)
            c_field = ("msids", args.c_field)
    
    if args.maude:
        mylog.info("Using MAUDE to retrieve MSID data.")
        ds = acispy.MaudeData(args.tstart, args.tstop, msids)
    else:
        ds = acispy.EngArchiveData(args.tstart, args.tstop,
                                   msids, stat='5min',
                                   filter_bad=True)
    
    if x_field[0] == "states" and y_field[0] != "states":
        ds.map_state_to_msid(x_field[1], y_field[1])
        x_field = ("msids", x_field[1])
    elif x_field[0] != "states" and y_field[0] == "states":
        ds.map_state_to_msid(y_field[1], x_field[1])
        y_field = ("msids", y_field[1])
    if args.c_field is not None:
        if c_field[0] == "states" and x_field[0] != "states":
            ds.map_state_to_msid(c_field[1], x_field[1])
        c_field = ("msids", c_field[1])
    
    if args.c_field is None:
        c_field = None
    
    pp = acispy.PhaseScatterPlot(ds, x_field, y_field, c_field=c_field, cmap=args.cmap)
    plt.show()


if __name__ == "__main__":
    main()