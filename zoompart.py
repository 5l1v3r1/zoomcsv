#! /usr/bin/python3
#! /home/robbie/software/anaconda3/bin/python

#  Purpose   : plot bar graph from Zoom video-meeting participant files
#  Author    : Robbie Morrison <robbie.morrison@posteo.de> / GitHub @robbiemorrison
#  Commenced : 16-Apr-2020
#  Status    : beta
#  Keywords  : python zoom participant-list

#  OPEN LICENSE
#
#  Copyright (c) 2020 Robbie Morrison <robbie.morrison@posteo.de>
#
#  SPDX-License-Identifier: ISC
#  License-Text:
#
#  ISC License
#
#  Permission to use, copy, modify, and/or distribute this software for any
#  purpose with or without fee is hereby granted, provided that the above
#  copyright notice and this permission notice appear in all copies.
#
#  The software is provided "as is" and the author disclaims all warranties
#  with regard to this software including all implied warranties of
#  merchantability and fitness.  In no event shall the author be liable for
#  any special, direct, indirect, or consequential damages or any damages
#  whatsoever resulting from loss of use, data or profits, whether in an
#  action of contract, negligence or other tortious action, arising out of
#  or in connection with the use or performance of this software.

# --------------------------------------
#  user defined variables
# --------------------------------------

# hardcoded here

numberedTitleFmt = "dummy workshop {0:02d} participation"             # used to create indexed title under option '--numbered-title'

# can be overwritten by command-line options

standinPlotTitle = "stand in title"                                   # used when no title is set on the command-line
cutoffDefault = 20                                                    # durations below this threshold in minutes are excluded in some participant counts

# --------------------------------------
#  version information
# --------------------------------------

versionStr = "0.3"                                                    # script version string

# -------------------------------------
#  modules
# -------------------------------------

import argparse                                   # argument parsing
import enum                                       # enumeration support
import os
import re                                         # support for regular expressions
import stat                                       # 'stat' (file status) results interpretation
import sys

import pandas
import datetime                                   # calculate timedelta intervals

# -------------------------------------
#  exit codes
# -------------------------------------

class ExitCode(enum.Enum):
    success  =   0                                # success
    failure  =   1                                # generic failure
    usage    =   2                                # command-line usage issue (the same as the argparse default)
    noFile   =  50                                # regular file not found
    datIssue =  51                                # DAT file issue

exitCode = ExitCode.success.value                 # presume success

# -------------------------------------
#  argument parsing
# -------------------------------------

description = "plot Zoom participant duration information"

# CAUTION: the 'epilog' is stripped of leading and trailing whitespace, so the usage here is acceptable

epilog = """

The utility plots duration infomation from the participant CSV file produced at
the end of a Zoom session.

Zoom is a proprietary video-conferencing application.  CSV indicates
comma-separated values format.

The resulting plot window can be either saved automatically using the
'--save-plot' option or saved manually as a SVG or PNG file from the plot
window.

A hardcoded custom numbered title is activated under option --numbered-title:
  "{0}"
The default plot title is:
  "{1}"

The short sessions cutoff under option --cutoff excludes sessions shorter than
the given threshold to provide an engaged participant count.

A DAT file contains the values used in the bar graph plot.  It does not contain
personal information, nor will any plot export files.

""".format(numberedTitleFmt, standinPlotTitle)

def argIsNatural(value):
    intvalue = int(value)
    if intvalue < 0:
        raise argparse.ArgumentTypeError("%s is not a non-negative integer" % value)
    return intvalue

parser = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawDescriptionHelpFormatter)

parser.add_argument('-V', '--version',                           action='version',                    version='%(prog)s ' + ' : ' + versionStr)
parser.add_argument('-t', '--title',            dest="title",    action='store',      required=False,                    help='plot title')
parser.add_argument('-n', '--numbered-title',   dest="number",   action='store',      required=False, type=argIsNatural, help='use custom numbered plot title')
parser.add_argument('-l', '--nominal-duration', dest="duration", action='store',      required=False, type=argIsNatural, help='set nominal duration in minutes')
parser.add_argument('-c', '--cutoff',           dest="cutoff",   action='store',      required=False, type=argIsNatural, help='set short session threshold in minutes')
parser.add_argument('-N', '--dedup-name',       dest="usename",  action='store_true', required=False,                    help='deduplicate on name not email address')
parser.add_argument('-d', '--dat-file',         dest="dat",      action='store_true', required=False,                    help='create or overwrite existing DAT file')
parser.add_argument('-P', '--no-plot',          dest="noplot",   action='store_true', required=False,                    help='omit plot')
parser.add_argument('-S', '--save-plot',        dest="saveplot", action='store_true', required=False,                    help='save plot automatically')
parser.add_argument('-T', '--truncate',         dest="length",   action='store',      required=False, type=argIsNatural, help='truncate input data for testing purposes')
parser.add_argument('-v', '--verbose',          dest="verbose",  action='store_true', required=False,                    help='show additional information')
parser.add_argument('-D', '--show-df',          dest="showdf",   action='store_true', required=False,                    help='show loaded dataframes')
parser.add_argument('csv',                      type=str,        action="store",                                         help='participant CSV file')

args = parser.parse_args()

# misuse of options

if args.title and args.number:
    raise argparse.ArgumentTypeError("cannot use options --title and --numbered-title simultaneously")
if args.noplot and args.saveplot:
    raise argparse.ArgumentTypeError("cannot use options --no-plot and --save-plot simultaneously")

# for convenience

plotTitle = args.title
titleNumber = args.number
nominalDuration = args.duration
givenCutoff = args.cutoff
useName = args.usename
createDatFile = args.dat
omitPlot = args.noplot
savePlotAlso = args.saveplot
csvTarget = args.csv

# -------------------------------------
#  report()
# -------------------------------------

def report(funcname='', key='', value=''):
    """convenient reporting function which acknowledges option '--verbose'

    * 'funcname' is hardcoded (it is difficult, but not impossible, to obtain the function name programmatically)
    * 'key' is a normally a string
    * 'value' is anything supported by the function 'str', it can be a string, int, or float, for example
    """

    funcname = str(funcname)
    key      = str(key)
    value    = str(value)
    if   value:    msg = '{0:<22s} : {1:<16s} : {2:s}'.format(funcname, key, value)
    elif key:      msg = '{0:<22s} : {1:s}'.format(funcname, key)
    elif funcname: msg = '{0:s}'.format(funcname)
    else:          msg = ''                   # effectively insert a blank line
    print(msg)

def deport(funcname='', key='', value=''):        # wrapper to 'report'
    if args.verbose:
        report(funcname, key, value)

# --------------------------------------
#  helper functions
# --------------------------------------

def pythonVer():                                  # print python version
    pyver = sys.version.splitlines()[0]
    deport("python version", pyver)

def scriptVer():                                  # print script version
    script = os.path.basename(sys.argv[0])
    report(script + " version", versionStr)

def setPandasWide():                              # allow full terminal output
    termrows, termcols = os.popen('stty size', 'r').read().split()
    termheight = int(termrows)
    termwidth = int(termcols)
    deport("stty rows x cols", '{0:d} x {1:d}'.format(termheight, termwidth))
    pandas.set_option('display.width', termwidth) # default width is 80
    pandaswidth = pandas.get_option('display.width')
    deport("pandas reporting width", pandaswidth)

def sayDf(df, stub, rows=5):                      # short report on given dataframe
    if not args.showdf:
        return
    info = "{0} = {1:d} x {2:d}".format(stub, df.shape[0], df.shape[1])
    report()
    report(info)
    print()
    if rows == 0: print(df)
    else        : print(df.head(rows))

def checkFile(regular):                           # check 'regular' that is a regular file with at least read permissions
    return os.path.isfile(regular) and os.access(regular, os.R_OK)

# read in CSV file meeting data
# Meeting ID | Topic | Start Time | End Time | User Email | Duration (Minutes) | Participants | Unnamed: 7

def readMeta(csvtarget):                          # read CSV metadata
    grab = 1
    df = pandas.read_csv(csvtarget, nrows=grab, parse_dates=['Start Time', 'End Time'])
    newcols = { 'Meeting ID'         : 'MeetingID',
                'Topic'              : 'Topic',
                'Start Time'         : 'Start',
                'End Time'           : 'Close',
                "User Email"         : "HostEmail",
                'Duration (Minutes)' : 'Minutes',
                'Participants'       : 'Count'}
    df = df.rename(columns=newcols)
    return df

def sayMeta(df):
    mid = df.at[0, 'MeetingID']
    topic =  df.at[0, 'Topic']
    start =  df.at[0, 'Start']
    close =  df.at[0, 'Close']
    minutes =  df.at[0, 'Minutes']
    count = df.at[0, 'Count']
    report()
    report("meeting ID", mid)
    report("stated topic", topic)
    report("meeting start", start)
    report("meeting close", close)
    report("duration minutes", minutes)
    report("duration hours", "{0:0.1f}".format(minutes/60.0))
    report("individual sessions", count)          # no attempt by Zoom to deduplicate

# read in CSV session data
# CSV columns : | Name (Original Name) | User Email | Join Time | Leave Time | Duration (Minutes) | Attentiveness Score |
# date parsing example: 03/26/2020 02:23:34 PM -> 2020-03-26 14:23:34

def readCsv(csvtarget):                           # read 'csvtarget' into a dataframe and return same
    csvskip = 2                                   # skip first 2 lines describing the meeting
    df = pandas.read_csv(csvtarget,
                         header=csvskip,
                         parse_dates=['Join Time', 'Leave Time'])
    newcols = { 'Name (Original Name)' : 'Name',
                'User Email'           : 'Email',
                'Join Time'            : 'Join',
                'Leave Time'           : 'Leaf',  # usefully 4 chars like "Join"
                'Duration (Minutes)'   : 'Minutes',
                'Attentiveness Score'  : 'Score'}
    df = df.rename(columns=newcols)
    return df

def truncateDf(df, rowslice):
    deport()
    deport("truncation active")
    deport()
    deport("row slice", "[:{0:d}]".format(rowslice))
    df = df[:rowslice]
    return df

def createSecondDf(df, mainkey):                  # create recipient dataframe and return same
    df2 = df.copy()
    df2 = df2[[mainkey]]                          # slice dataframe using 'mainkey'
    df2 = df2.drop_duplicates(keep='first')       # remove duplicate rows
    df2 = df2.sort_values(by=[mainkey])           # sort
    df2 = df2.reset_index(drop=True)              # CAUTION: reindex essential, 'drop' means do not try to insert new index into a dataframe column
    df2['Join'] = None                            # add new column and initialize to nothing
    df2['Leaf'] = None                            # add new column and initialize to nothing
    df2['Delta'] = 0                              # add new column and initialize to integer zero
    return df2

# loop original dataframe and ratchet up cumulative minutes in recipient dataframe
# iterating over dataframes is not good practice but it will do for now

def stockSecondDf(df, df2, mainkey):                                  # load recipient dataframe and return same
    # stocking code
    deport()
    deport("stocking loop")
    for index, row in df.iterrows():
        # get original data
        value = row[mainkey]
        join = row['Join']
        leaf = row['Leaf']
        # get, process, and set recipient data
        rowindex2 = df2.index[df2[mainkey] == value].tolist()[0]      # list never more than one item
        colindex2join = df2.columns.get_loc('Join')                   # returns zero-based index
        colindex2leaf = df2.columns.get_loc('Leaf')
        currentjoin = df2.iat[rowindex2, colindex2join]               # get current join time
        currentleaf = df2.iat[rowindex2, colindex2leaf]               # get current leaf time
        if currentjoin == None:
            df2.iat[rowindex2, colindex2join] = join                  # set new join time
        elif join < currentjoin:
            df2.iat[rowindex2, colindex2join] = join                  # ratchet down join time
        if currentleaf == None:
            df2.iat[rowindex2, colindex2leaf] = leaf                  # set new leaf time
        elif leaf > currentleaf:
            df2.iat[rowindex2, colindex2leaf] = leaf                  # ratchet up leaf time
    # duration calculations
    deport()
    deport("duration loop")
    for index2, row2 in df2.iterrows():
        join2 = row2['Join']
        leaf2 = row2['Leaf']
        duration = leaf2 - join2                                      # datetime.timedelta object
        minutes = duration.total_seconds() / 60.0                     # floating point-valued
        colindex2delta = df2.columns.get_loc('Delta')                 # returns zero-based index
        df2.iat[index2, colindex2delta] = minutes                     # integer-valued

    df2 = df2.sort_values(by=['Delta'])                               # sort
    return df2

def extractCol(df, fieldname, cutoff):                                # extract a column and return as list
    mysep = "\n"                                                      # one value per line
    report()
    column = df[fieldname].tolist()
    column.sort()                                                     # redundant statement in this use case
    participants = len(column)
    report("participants", participants)
    cutlen = sum(1 for i in column if i >= cutoff)
    report ("stayed " + str(cutoff) + " or more", cutlen)
    return column

def getStub():                                    # generate stub name for creating files
    deport()
    script = os.path.basename(sys.argv[0])
    stub_1 = os.path.splitext(script)[0]          # based on script name
    stub_2 = re.sub(' +', '-', plotTitle)         # based on plot title
    stub_2 = stub_2.lower()                       # downcase
    stub = stub_2                                 # control which 'stub' to use here
    deport("filename stub", stub)
    return stub

def writeDatFile(filename, data, sep):           # create DAT file
    deport()
    deport("creating DAT file")
    deport()
    deport("DAT file", filename)
    if os.path.isfile(filename): xeport("writeDatFile", "action", "overwriting exiting file")
    else:                        xeport("writeDatFile", "action", "creating new file")
    # active code
    try:
        userwritePerms = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP   # set file permission to 0640
        readonlyPerms = stat.S_IRUSR | stat.S_IRGRP                   # set file permission to 0440
        if os.path.isfile(filename):                                  # file may not exist at this juncture
            os.chmod(filename, userwritePerms)
        fd = open(filename, 'w')
        print(*data, sep=sep, file=fd)
        fd.close()
        os.chmod(filename, readonlyPerms)
    except IOError:
        xeport("file open error", filename)
        exitCode = ExitCode.datIssue.value                            # update exit code

def mvSvgCall(localSvg):                          # useful reporting
    default = "Figure_1.svg"
    mvcall = "mv ~/{0:s} {1:s} && chmod 0440 {1:s}".format(default, localSvg)
    deport("convenient move call", mvcall)

def myexit(exitcode):                             # common point of exit
    deport()
    deport("script", "complete")
    if exitcode == 0: deport("exit code", str(exitcode) + " (success)")
    else:             deport("exit code", str(exitcode) + " (failure)")
    report()
    sys.exit(exitcode)

# --------------------------------------
#  plotting function
# --------------------------------------

def plotList(column, plottitle, stub):

    import matplotlib.pyplot as plt

    persons = len(column)
    title = plottitle
    xlabel = "person number (count {0:d})".format(persons)
    ylabel = "duration [minutes]"
    annot = "nominal duration"

    report("plot title", title)
    deport("persons", persons)

    plt.figure(figsize=(8,6), dpi=200)                                # 'figsize' in inches, default 'dpi' is 80
    bar = plt.bar(range(len(cumulatives)), cumulatives)               # bar graph not histogram

    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)

    if nominalDuration:                                               # overplot horizontal line
        # overplot line
        nomLen = int(nominalDuration)
        report("nominal duration line", nomLen)
        plt.axhline(y=nomLen, color='black', linestyle='dotted')
        # add annotation
        offset = 0
        annot = "{0:s} {1:d}".format(annot, nomLen)
        deport("label offset", offset)
        plt.annotate(annot, [offset, nomLen + 5])

    plt.show()

    if savePlotAlso:
        svgFilename = stub + ".svg"
        plt.savefig(filename=svgFilename, format='svg')               # this provided an empty plot for some reason, so instead save manually from plot window

# --------------------------------------
#  active code
# --------------------------------------

# outset reporting

report()                                          # add initial blank line
scriptVer()                                       # print script version
deport("verbose", "on")                           # report debug status
if args.showdf: deport("show dataframes", "on")
if args.length: deport("truncate", "active")
pythonVer()                                       # print python version
report("target", csvTarget)

# improve pandas terminal reporting

if not sys.platform == 'win32':
    setPandasWide()                               # possibly contains OS-specific code?

# process title

if titleNumber: plotTitle = numberedTitleFmt.format(titleNumber)
if plotTitle:   plotTitle = plotTitle.strip()
else:           plotTitle = standinPlotTitle
report("processed title", plotTitle)

# process deduplication key

if useName: participantKey = 'Name'               # deduplicate by name, less reliable as subsequent attempts may use different string
else:       participantKey = 'Email'              # deduplicate by email address
report("deduplication key", "'" + participantKey + "'")

# process cutoff

if givenCutoff: cutoff = givenCutoff
else:           cutoff = cutoffDefault            # revert to default
report ("cutoff minutes", cutoff)

# check CSV file exists and is readable

if not checkFile(csvTarget):
    report("absent or unreadable", csvTarget)
    myexit(ExitCode.noFile.value)

# read in CSV file and report

meta = readMeta(csvTarget)
sayDf(meta, "meta dataframe")
sayMeta(meta)

df = readCsv(csvTarget)
sayDf(df, "original dataframe")

# truncate for development purposes as required

if args.length:
    df = truncateDf(df, args.length)

# create recipient dataframe and report

df2 = createSecondDf(df, participantKey)
sayDf(df2, "deduplicated dataframe")

# stock recipient dataframe and report

df2 = stockSecondDf(df, df2, participantKey)
sayDf(df2, "ratcheted dataframe", 0)              # zero is print entire dataframe

# extract column and report

cumulatives = extractCol(df2, 'Delta', cutoff)

# sum the deltas and report

cumminutes = sum(cumulatives)
cumhours = cumminutes/60.0
cumhourstr = format("%0.1f" % (cumhours))
report("cumulative hours", cumhourstr)

# print column to file as required

if createDatFile:
    stub = getStub()
    mysep = "\n"                                  # one value per line
    writeDatFile(stub + ".dat", cumulatives, mysep)

# plot as required

report()
if omitPlot:
    deport("omitting plot")
else:
    deport("creating plot")
    stub = getStub()
    plotList(cumulatives, plotTitle, stub)
    if not savePlotAlso:
        mvSvgCall(stub + ".svg")                  # passive reporting only

# -------------------------------------
#  housekeeping
# -------------------------------------

myexit(exitCode)

# end of file
