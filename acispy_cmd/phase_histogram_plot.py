#!/usr/bin/env python

import matplotlib
import matplotlib.pyplot as plt
import argparse
import acispy
from acispy.utils import state_labels, mylog
matplotlib.use("Qt5Agg")

def main():
    
    parser = argparse.ArgumentParser(description='Make a phase plot of one MSID or state versus another within a certain time frame.')
    parser.add_argument("tstart", type=str, help='The start time in YYYY:DOY:HH:MM:SS format')
    parser.add_argument("tstop", type=str, help='The stop time in YYYY:DOY:HH:MM:SS format')
    parser.add_argument("x_field", type=str, help='The MSID or state to plot on the x-axis')
    parser.add_argument("y_field", type=str, help='The MSID or state to plot on the y-axis')
    parser.add_argument("x_bins", type=int, help='The number of bins on the x-axis')
    parser.add_argument("y_bins", type=int, help='The number of bins on the y-axis')
    parser.add_argument("--scale", type=str, default="linear", help="Use linear or log scaling for the histogram, default 'linear'")
    parser.add_argument("--cmap", type=str, default="hot", help="The colormap for the histogram, default 'hot'")
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
    
    pp = acispy.PhaseHistogramPlot(ds, args.x_field, args.y_field, args.x_bins, args.y_bins, 
                                   scale=args.scale, cmap=args.cmap)
    plt.show()


if __name__ == "__main__":
    main()