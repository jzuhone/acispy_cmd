#!/usr/bin/env python

import matplotlib
import matplotlib.pyplot as plt
import argparse
import acispy
from acispy.utils import state_labels
matplotlib.use("Qt5Agg")


def main():
    
    parser = argparse.ArgumentParser(description='Plot a single model component with another component or state')
    parser.add_argument("load", type=str, help='The load to take the model from')
    parser.add_argument("y_axis", type=str, help='The model component to plot on the left y-axis')
    parser.add_argument("--y2_axis", type=str, help="The model component or state to plot on the right y-axis (default: none)")
    args = parser.parse_args()
    
    if args.y_axis in state_labels:
        y_axis = ("states", args.y_axis)
    else:
        y_axis = ("model", args.y_axis)
    if args.y2_axis is not None:
        if args.y2_axis in state_labels:
            y2_axis = ("states", args.y2_axis)
        else:
            y2_axis = ("model", args.y2_axis)
    else:
        y2_axis = None
    
    ds = acispy.ThermalModelFromLoad(args.load, args.y_axis)
    cp = acispy.DatePlot(ds, y_axis, field2=y2_axis)
    plt.show()


if __name__ == "__main__":
    main()