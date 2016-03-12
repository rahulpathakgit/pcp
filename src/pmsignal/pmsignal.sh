#!/bin/sh
# 
# Copyright (c) 2014,2016 Red Hat.
# Copyright (c) 2009 Aconex.  All Rights Reserved.
# 
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
# 
# Cross-platform signal/event sender for Performance Co-Pilot utilities.
# Supports a minimal set of signals, used by PCP tools on all platforms.
#

. $PCP_DIR/etc/pcp.env

status=1
tmp=`mktemp -d /tmp/pcp.XXXXXXXXX` || exit 1
trap "rm -rf $tmp; exit \$status" 0 1 2 3 15
prog=`basename $0`
sigs="HUP USR1 TERM KILL"

cat > $tmp/usage << EOF
# Usage: [options] PID ... | name ...

Options:
  -a,--all          send signal to all named processes (killall mode)
  -l,--list         list available signals
  -n,--dry-run      list processes that would be affected
  -p,--program      extract process identifiers from $PCP_RUN_DIR programs
  -s=N,--signal=N   signal to send ($sigs)"
  --help
EOF

usage()
{
    [ ! -z "$@" ] && echo $@ 1>&2
    pmgetopt --progname=$prog --config=$tmp/usage --usage
    exit 1
}

check()
{
    for sig in $sigs
    do
	[ $sig = "$1" ] && echo $sig && return
    done
    usage "$prog: invalid signal - $1"
}

signal=TERM
pmsignal=""
aflag=false
lflag=false
nflag=false
pflag=false

ARGS=`pmgetopt --progname=$prog --config=$tmp/usage -- "$@"`
[ $? != 0 ] && exit 1

eval set -- "$ARGS"
while [ $# -gt 0 ]
do
    case "$1"
    in
	-a)	aflag=true ;;
	-l)	lflag=true ;;
	-n)	nflag=true ;;
	-p)	pflag=true ;;
	-s)	signal=`check "$2"`
		shift
		;;
	--)	shift
		break
		;;
	-\?)	usage ""
		;;
    esac
    shift
done

$lflag && echo "$sigs" && exit 0

[ $aflag = true -a $pflag = true ] && \
    usage "$prog: Cannot specify both \"all\" and \"program\" modes"
[ $# -lt 1 ] && usage "$prog: Insufficient arguments"

if $aflag
then
    pids=""
    for name in "$@"; do
	program=`basename "$name"`
	pidlist=`_get_pids_by_name "$program"`
	pids="$pids $pidlist"
    done
elif $pflag
then
    pids=""
    for name in "$@"; do
	program=`basename "$name"`
	pidlist=`cat "$PCP_RUN_DIR/${program}.pid" 2>/dev/null`
	pids="$pids $pidlist"
    done
else
    pids="$@"
fi
$nflag && pmsignal=echo

sts=0
if [ "$PCP_PLATFORM" = mingw ]
then
    for pid in $pids ; do
	$pmsignal pcp-setevent $signal $pid
	[ $? -eq 0 ] || sts=$?
    done
else
    for pid in $pids ; do
	$pmsignal kill -$signal $pid
	[ $? -eq 0 ] || sts=$?
    done
fi

status=$sts
exit
