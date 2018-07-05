#!/usr/bin/env python
#
# Author: Sergei Franco (sergei at sergei.nz)
# License: GPL3 
# Warranty: NONE! Use at your own risk!
# Disclaimer: I am no programmer!
# Description: this script will crudely extract embedded GPS data from Novatek generated MP4 files.
#

# Modded by EgorKin (egorkin at gmail.com)
# Add include (-i) files by mask or directory to parse multiple files without combine MP4 video files in video editor software
# Add show help by run script w/o arguments

import os, struct, sys, argparse, glob

gps_data = []
gpx = ''
in_file = ''
out_file = ''
force = False

def check_out_file(out_file,force):
    if os.path.isfile(out_file) and not force:
        print("Error specified out file '%s' exists, specify '-f' to overwrite it!" % out_file)
        sys.exit(1)
        
def check_in_file(in_file):
    in_files=[]
    for f in in_file:
        # glob needed if for some reason quoted glob is passed, or script is run on the most popular proprietary inferior OS
        for f1 in glob.glob(f):
                if os.path.isdir(f1):
                    print("Directory '%s' specified as input, listing..." % f1)
                    for f2 in os.listdir(f1):
                        f3 = os.path.join(f1,f2)
                        if os.path.isfile(f3):
                            print(f3.rsplit(".",1))
                            if f3.rsplit(".",1)[1].upper()=="MP4":
                                print("Queueing file '%s' for processing..." % f3)
                                in_files.append(f3)
                elif os.path.isfile(f1):
                    print(f1.rsplit(".",1))
                    if f1.rsplit(".",1)[1].upper()=="MP4":				
                        print("Queueing file '%s' for processing..." % f1)
                        in_files.append(f1)
                else:
                    # Catch all for typos...
                    print("Skipping invalid input '%s'..." % f1)
    # sort files by name but ignore last part "_nnn.MP4"
    in_files = sorted(in_files, key = lambda x: x[:-8])
    return in_files

def get_args():
    p = argparse.ArgumentParser(add_help=True, description='This script will attempt to extract GPS data from Novatek MP4 file and output it in GPX format.')
    p.add_argument('-i',metavar='input',nargs='+',help='input file(s), globs (eg: *) or directory(ies)')
    p.add_argument('-o',metavar='output',nargs=1,help='output file (single)')
    p.add_argument('-f',action='store_true',help='overwrite output file if exists')
    if len(sys.argv)==1:
        p.print_help(sys.stderr)
        sys.exit(1)
    args=p.parse_args(sys.argv[1:])
    in_file=check_in_file(args.i)
    if args.o:
        out_file=args.o[0]
    elif in_file:
        out_file=in_file[0]+'.gpx'
    else:
        out_file=''
    check_out_file(out_file,args.f)

    return (in_file,out_file)



def fix_time(hour,minute,second,year,month,day):
    return "%d-%02d-%02dT%02d:%02d:%02dZ" % ((year+2000),int(month),int(day),int(hour),int(minute),int(second))

def fix_coordinates(hemisphere,coordinate):
    # Novatek stores coordinates in odd DDDmm.mmmm format
    minutes = coordinate % 100.0
    degrees = coordinate - minutes
    coordinate = degrees / 100.0 + (minutes / 60.0)
    if hemisphere == 'S' or hemisphere == 'W':
        return -1*float(coordinate)
    else:
        return float(coordinate)

def fix_speed(speed):
    # 1 knot = 0.514444 m/s
    return speed * float(0.514444)

def get_atom_info(eight_bytes):
    try:
        atom_size,atom_type=struct.unpack('>I4s',eight_bytes)
    except struct.error:
        return 0,''
    return int(atom_size),atom_type.decode()

def get_gps_atom_info(eight_bytes):
    atom_pos,atom_size=struct.unpack('>II',eight_bytes)
    return int(atom_pos),int(atom_size)

def get_gps_atom(gps_atom_info,f):
    atom_pos,atom_size=gps_atom_info
    f.seek(atom_pos)
    data=f.read(atom_size)
    expected_type='free'
    expected_magic='GPS '
    atom_size1,atom_type,magic=struct.unpack_from('>I4s4s',data)
    atom_type=atom_type.decode()
    magic=magic.decode()
    #sanity:
    if atom_size != atom_size1 or atom_type != expected_type or magic != expected_magic:
        print("Error! skipping atom at %x (expected size:%d, actual size:%d, expected type:%s, actual type:%s, expected magic:%s, actual maigc:%s)!" % (int(atom_pos),atom_size,atom_size1,expected_type,atom_type,expected_magic,magic))
        return

    hour,minute,second,year,month,day,active,latitude_b,longitude_b,unknown2,latitude,longitude,speed = struct.unpack_from('<IIIIIIssssfff',data, 48)
    active=active.decode()
    latitude_b=latitude_b.decode()
    longitude_b=longitude_b.decode()

    time=fix_time(hour,minute,second,year,month,day)
    latitude=fix_coordinates(latitude_b,latitude)
    longitude=fix_coordinates(longitude_b,longitude)
    speed=fix_speed(speed)

    #it seems that A indicate reception
    if active != 'A':
        print("Skipping: lost GPS satelite reception. Time: %s." % time)
        return

    return (latitude,longitude,time,speed)

def get_gpx(gps_data,out_file):
    gpx  = '<?xml version="1.0" encoding="UTF-8"?>\n'
    gpx += '<gpx version="1.0"\n'
    gpx += '\tcreator="Sergei\'s Novatek MP4 GPS parser"\n'
    gpx += '\txmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n'
    gpx += '\txmlns="http://www.topografix.com/GPX/1/0"\n'
    gpx += '\txsi:schemaLocation="http://www.topografix.com/GPX/1/0 http://www.topografix.com/GPX/1/0/gpx.xsd">\n'
    gpx += "\t<name>%s</name>\n" % out_file
    gpx += '\t<url>sergei.nz</url>\n'
    gpx += "\t<trk><name>%s</name><trkseg>\n" % out_file
    for l in gps_data:
        if l:
            gpx += "\t\t<trkpt lat=\"%f\" lon=\"%f\"><time>%s</time><speed>%f</speed></trkpt>\n" % l
    gpx += '\t</trkseg></trk>\n'
    gpx += '</gpx>\n'
    return gpx


def process_file(in_file):
    global gps_data
    print("Processing file '%s'..." % in_file)
    with open(in_file, "rb") as f:
        offset = 0
        while True:
            atom_pos = f.tell()
            atom_size, atom_type = get_atom_info(f.read(8))
            if atom_size == 0:
                break

            if atom_type == 'moov':
                print("Found moov atom...")
                sub_offset = offset+8

                while sub_offset < (offset + atom_size):
                    sub_atom_pos = f.tell()
                    sub_atom_size, sub_atom_type = get_atom_info(f.read(8))

                    if str(sub_atom_type) == 'gps ':
                        print("Found gps chunk descriptor atom...")
                        gps_offset = 16 + sub_offset # +16 = skip headers
                        f.seek(gps_offset,0)
                        while gps_offset < ( sub_offset + sub_atom_size):
                            gps_data.append(get_gps_atom(get_gps_atom_info(f.read(8)),f))
                            gps_offset += 8
                            f.seek(gps_offset,0)

                    sub_offset += sub_atom_size
                    f.seek(sub_offset,0)

            offset += atom_size
            f.seek(offset,0)
def main():
    in_files,out_file=get_args()
    for f in in_files:
        process_file(f)

    gpx=get_gpx(gps_data,out_file)

    if gpx:
        with open (out_file, "w") as f:
            print("Wiriting data to output file '%s'" % out_file)
            f.write(gpx)
    else:
        print("GPS data not found...")
        sys.exit(1)

    print("Success!")
    
if __name__ == "__main__":
    main()
