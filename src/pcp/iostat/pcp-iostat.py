#!/usr/bin/env pmpython
#
# Copyright (C) 2014-2016 Red Hat.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Iostat Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#
# pylint: disable=C0103,R0914,R0902
""" Display disk and device-mapper I/O statistics """

import sys
import signal
from pcp import pmapi, pmcc
from cpmapi import PM_TYPE_U64, PM_CONTEXT_ARCHIVE, PM_SPACE_KBYTE, PM_MODE_FORW

# use default SIGPIPE handler to avoid broken pipe exceptions
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

IOSTAT_SD_METRICS = [ 'disk.dev.read', 'disk.dev.read_bytes',
                 'disk.dev.write', 'disk.dev.write_bytes',
                 'disk.dev.read_merge', 'disk.dev.write_merge',
                 'disk.dev.blkread', 'disk.dev.blkwrite',
                 'disk.dev.read_rawactive', 'disk.dev.write_rawactive',
                 'disk.dev.avactive']

IOSTAT_DM_METRICS = [ 'disk.dm.read', 'disk.dm.read_bytes',
                 'disk.dm.write', 'disk.dm.write_bytes',
                 'disk.dm.read_merge', 'disk.dm.write_merge',
                 'disk.dm.blkread', 'disk.dm.blkwrite',
                 'disk.dm.read_rawactive', 'disk.dm.write_rawactive',
                 'disk.dm.avactive']

class IostatReport(pmcc.MetricGroupPrinter):
    Hcount = 0
    def timeStampDelta(self, group):
        c = 1000000.0 * group.timestamp.tv_sec + group.timestamp.tv_usec
        p = 1000000.0 * group.prevTimestamp.tv_sec + group.prevTimestamp.tv_usec
        return (c - p) / 1000000.0

    def instlist(self, group, name):
        return dict(map(lambda x: (x[1], x[2]), group[name].netValues)).keys()

    def curVals(self, group, name):
        return dict(map(lambda x: (x[1], x[2]), group[name].netValues))

    def prevVals(self, group, name):
        return dict(map(lambda x: (x[1], x[2]), group[name].netPrevValues))

    def report(self, manager):
        if 'dm' in IostatOptions.xflag:
            subtree = 'disk.dm'
        else:
            subtree = 'disk.dev'
        group = manager["iostat"]

        if group[subtree + '.read_merge'].netPrevValues == None:
            # need two fetches to report rate converted counter metrics
            return

        instlist = self.instlist(group, subtree + '.read')
        dt = self.timeStampDelta(group)
        timestamp = group.contextCache.pmCtime(int(group.timestamp)).rstrip()

        c_rrqm = self.curVals(group, subtree + '.read_merge')
        p_rrqm = self.prevVals(group, subtree + '.read_merge')

        c_wrqm = self.curVals(group, subtree + '.write_merge')
        p_wrqm = self.prevVals(group, subtree + '.write_merge')

        c_r = self.curVals(group, subtree + '.read')
        p_r = self.prevVals(group, subtree + '.read')

        c_w = self.curVals(group, subtree + '.write')
        p_w = self.prevVals(group, subtree + '.write')

        c_rkb = self.curVals(group, subtree + '.read_bytes')
        p_rkb = self.prevVals(group, subtree + '.read_bytes')

        c_wkb = self.curVals(group, subtree + '.write_bytes')
        p_wkb = self.prevVals(group, subtree + '.write_bytes')

        c_ractive = self.curVals(group, subtree + '.read_rawactive')
        p_ractive = self.prevVals(group, subtree + '.read_rawactive')

        c_wactive = self.curVals(group, subtree + '.write_rawactive')
        p_wactive = self.prevVals(group, subtree + '.write_rawactive')

        c_avactive = self.curVals(group, subtree + '.avactive')
        p_avactive = self.prevVals(group, subtree + '.avactive')

        if "t" in IostatOptions.xflag:
            headfmt = "%-24s %-12s %7s %7s %6s %6s %8s %8s %8s %8s %7s %7s %7s %5s"
            valfmt = "%-24s %-12s %7.1f %7.1f %6.1f %6.1f %8.1f %8.1f %8.2f %8.2f %7.1f %7.1f %7.1f %5.1f"
        else:
            headfmt = "%-12s %7s %7s %6s %6s %8s %8s %8s %8s %7s %7s %7s %5s"
            valfmt = "%-12s %7.1f %7.1f %6.1f %6.1f %8.1f %8.1f %8.2f %8.2f %7.1f %7.1f %7.1f %5.1f"

        if "h" not in IostatOptions.xflag:
            self.Hcount += 1
            if self.Hcount == 24:
                self.Hcount = 1
            if self.Hcount == 1:
                if "t" in IostatOptions.xflag:
                    heading = ('# Timestamp', 'Device', 'rrqm/s', 'wrqm/s', 'r/s', 'w/s', 'rkB/s', 'wkB/s',
                               'avgrq-sz', 'avgqu-sz', 'await', 'r_await', 'w_await', '%util')
                else:
                    heading = ('# Device', 'rrqm/s', 'wrqm/s', 'r/s', 'w/s', 'rkB/s', 'wkB/s',
                               'avgrq-sz', 'avgqu-sz', 'await', 'r_await', 'w_await', '%util')
                print(headfmt % heading)

        if p_rrqm == {} or p_wrqm == {} or p_r == {} or p_w == {} or \
           p_ractive == {} or p_wactive == {} or p_avactive == {} or \
           p_rkb == {} or p_wkb == {}:
            # no values for some metric (e.g. near start of archive)
            if "t" in IostatOptions.xflag:
                print(headfmt % (timestamp, 'NODATA', '?', '?', '?', '?', '?', '?','?', '?', '?', '?', '?', '?'))
            return

        try:
            for inst in sorted(instlist):
                # basic stats
                rrqm = (c_rrqm[inst] - p_rrqm[inst]) / dt
                wrqm = (c_wrqm[inst] - p_wrqm[inst]) / dt
                r = (c_r[inst] - p_r[inst]) / dt
                w = (c_w[inst] - p_w[inst]) / dt
                rkb = (c_rkb[inst] - p_rkb[inst]) / dt
                wkb = (c_wkb[inst] - p_wkb[inst]) / dt

                # totals
                tot_rios = (float)(c_r[inst] - p_r[inst])
                tot_wios = (float)(c_w[inst] - p_w[inst])
                tot_ios = (float)(tot_rios + tot_wios)

                # total active time in seconds (same units as dt)
                tot_active = (float)(c_avactive[inst] - p_avactive[inst]) / 1000.0

                avgrqsz = avgqsz = await = r_await = w_await = util = 0.0

                # average request size units are KB (sysstat reports in units of sectors)
                if tot_ios:
                    avgrqsz = (float)((c_rkb[inst] - p_rkb[inst]) + (c_wkb[inst] - p_wkb[inst])) / tot_ios

                # average queue length
                avgqsz = (float)((c_ractive[inst] - p_ractive[inst]) + (c_wactive[inst] - p_wactive[inst])) / dt / 1000.0

                # await, r_await, w_await
                if tot_ios:
                    await = ((c_ractive[inst] - p_ractive[inst]) + (c_wactive[inst] - p_wactive[inst])) / tot_ios

                if tot_rios:
                    r_await = (c_ractive[inst] - p_ractive[inst]) / tot_rios

                if tot_wios:
                    w_await = (c_wactive[inst] - p_wactive[inst]) / tot_wios

                # device utilization (percentage of active time / interval)
                if tot_active:
                    util = 100.0 * tot_active / dt

                device = inst	# prepare name for printing
                badcounters = rrqm < 0 or wrqm < 0 or r < 0 or w < 0 or await < 0 or avgrqsz < 0 or avgqsz < 0 or util < 0

                if "t" in IostatOptions.xflag:
                    if badcounters:
                        print(headfmt % (timestamp, device, '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?'))
                    else:
                        print(valfmt % (timestamp, device, rrqm, wrqm, r, w, rkb, wkb, avgrqsz, avgqsz, await, r_await, w_await, util))
                else:
                    if badcounters:
                        print(headfmt % (device, '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?'))
                    else:
                        print(valfmt % (device, rrqm, wrqm, r, w, rkb, wkb, avgrqsz, avgqsz, await, r_await, w_await, util))
        except KeyError:
            # instance missing from previous sample
            pass

class IostatOptions(pmapi.pmOptions):
    # class attributes
    xflag = [] 
    uflag = None
    Pflag = 2

    def checkOptions(self, manager):
        if IostatOptions.uflag:
            if manager._options.pmGetOptionInterval():
                print("Error: -t incompatible with -u")
                return False
            if manager.type != PM_CONTEXT_ARCHIVE:
                print("Error: -u can only be specified with -a archive")
                return False
        return True

    def extraOptions(self, opt, optarg, index):
        if opt == "x":
            IostatOptions.xflag += optarg.replace(',', ' ').split(' ')
        elif opt == "u":
            IostatOptions.uflag = True
        elif opt == "P":
            IostatOptions.Pflag = int(optarg)

    def __init__(self):
        pmapi.pmOptions.__init__(self, "A:a:D:h:O:P:S:s:T:t:uVZ:z?x:")
        self.pmSetOptionCallback(self.extraOptions)
        self.pmSetLongOptionHeader("General options")
        self.pmSetLongOptionAlign()
        self.pmSetLongOptionArchive()
        self.pmSetLongOptionDebug()
        self.pmSetLongOptionHost()
        self.pmSetLongOptionOrigin()
        self.pmSetLongOption("precision", 1, "P", "N", "N digits after the decimal separator")
        self.pmSetLongOptionStart()
        self.pmSetLongOptionSamples()
        self.pmSetLongOptionFinish()
        self.pmSetLongOptionInterval()
        self.pmSetLongOption("no-interpolation", 0, "u", "", "disable interpolation mode with archives")
        self.pmSetLongOptionVersion()
        self.pmSetLongOptionTimeZone()
        self.pmSetLongOptionHostZone()
        self.pmSetLongOptionHelp()
        self.pmSetLongOptionHeader("Extended options")
        self.pmSetLongOption("", 1, 'x', "LIST", "comma separated extended options: [[dm],[t],[h]]")
        self.pmSetLongOptionText("\t\tdm\tshow device-mapper statistics (default is sd devices)")
        self.pmSetLongOptionText("\t\tt\tprecede every line with a timestamp in ctime format");
        self.pmSetLongOptionText("\t\th\tsuppress headings");

if __name__ == '__main__':
    try:
        opts = IostatOptions()
        manager = pmcc.MetricGroupManager.builder(opts, sys.argv)
        if not opts.checkOptions(manager):
            raise pmapi.pmUsageErr

        if IostatOptions.uflag:
            # -u turns off interpolation
            manager.pmSetMode(PM_MODE_FORW, manager._options.pmGetOptionOrigin(), 0)

        if "dm" in IostatOptions.xflag :
            manager["iostat"] = IOSTAT_DM_METRICS
        else:
            manager["iostat"] = IOSTAT_SD_METRICS
        manager.printer = IostatReport()
        sts = manager.run()
        sys.exit(sts)
    except pmapi.pmErr as error:
        sys.stderr.write('%s: %s\n' % (error.progname(), error.message()))
    except pmapi.pmUsageErr as usage:
        usage.message()
        sys.exit(1)
    except KeyboardInterrupt:
        pass
