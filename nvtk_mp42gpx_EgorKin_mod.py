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
# 19.07.2018 - Add course tag support
# 25.09.2018 - Add new searching GPS data algo, useful for some files w/o gps chunks in 'moov' section. IMHO can find GPS data in ANY file if data is present.
#            - Add MOV to file extension list
# 21.05.2021: add unknown_new = 0x03F0 and change offset from 48 to 12 for new VIOFO A129 Plus (Duo)
# 05.07.2022: add unknown_new = 0x58 and change offset to 0x30 for new VIOFO A229


import os, struct, sys, argparse, glob

gps_chunk_offsets = []
gps_data = []
gpx = ''
in_file = ''
out_file = ''
force = False

CounterFreeGPS = 0
CounterGPSChunk = 0

CounterValidGPSChunk = 0
CounterValidFreeGPS = 0
# for chunks and for freeGPS too
CounterSkipLostGPSChunk = 0
CounterSkipLostFreeGPS = 0

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
                            #print(f3.rsplit(".",1))
                            if f3.rsplit(".",1)[1].upper()=="MP4" or f3.rsplit(".",1)[1].upper()=="MOV":
                                print("Queueing file '%s' for processing..." % f3)
                                in_files.append(f3)
                elif os.path.isfile(f1):
                    #print(f1.rsplit(".",1))
                    if f1.rsplit(".",1)[1].upper()=="MP4" or f1.rsplit(".",1)[1].upper()=="MOV":
                        print("Queueing file '%s' for processing..." % f1)
                        in_files.append(f1)
                else:
                    # Catch all for typos...
                    print("Skipping invalid input '%s'..." % f1)
    # sort files by name but ignore last part "_nnn.MP4"
    in_files = sorted(in_files, key = lambda x: x[:-8])
    return in_files

def get_args():
    p = argparse.ArgumentParser(add_help=True, description='This script will attempt to extract GPS data from dashcam video files and output it in GPX format.')
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
    try:
        a_t = atom_type.decode()
    except UnicodeDecodeError:
        a_t = 'UNKNOWN'
    return int(atom_size),a_t

def get_gps_atom_info(eight_bytes):
    atom_pos,atom_size=struct.unpack('>II',eight_bytes)
    return int(atom_pos),int(atom_size)

def get_gps_atom(gps_atom_info,f):
    atom_pos,atom_size=gps_atom_info
    print("Atom pos = %x, atom size = %x" % (atom_pos,atom_size));
    try:
        f.seek(atom_pos)
        data=f.read(atom_size)
    except OverflowError as e:
        print("Skipping at %x: seek or read error. Error: %s." % (int(atom_pos), str(e)))
        return
    expected_type='free'
    expected_magic='GPS '
    atom_size1,atom_type,magic=struct.unpack_from('>I4s4s',data)
    try:
        atom_type=atom_type.decode()
        magic=magic.decode()
        #sanity:
        if atom_size != atom_size1 or atom_type != expected_type or magic != expected_magic:
            print("Error! skipping atom at %x (expected size:%d, actual size:%d, expected type:%s, actual type:%s, expected magic:%s, actual maigc:%s)!" % (int(atom_pos),atom_size,atom_size1,expected_type,atom_type,expected_magic,magic))
            return
    except UnicodeDecodeError as e:
        print("Skipping at %x: garbage atom type or magic. Error: %s." % (int(atom_pos), str(e)))
        return

    # > - big-endian    < - little-endian
    #21.05.2021: add unknown_new = 0x03F0
    #05.07.2022: add unknown_new = 0x58
    #was: hour,minute,second,year,month,day,active,latitude_b,longitude_b,unknown2,latitude,longitude,speed,course = struct.unpack_from('<IIIIIIIssssffff',data, 48)
    unknown_new = struct.unpack_from('<I',data, 12)
    #print("unknown_new = %x" % unknown_new[0])
    if unknown_new[0] == 0x58:
        hour,minute,second,year,month,day,active,latitude_b,longitude_b, unknown2,latitude,longitude,speed,course = struct.unpack_from('<IIIIIIssssffff',data, 0x30)
    else:
        if unknown_new[0] == 0x3F0:
            hour,minute,second,year,month,day,active,latitude_b,longitude_b, unknown2,latitude,longitude,speed,course = struct.unpack_from('<IIIIIIssssffff',data, 0x10)
        else:
            hour,minute,second,year,month,day,active,latitude_b,longitude_b,unknown2,latitude,longitude,speed,course = struct.unpack_from('<IIIIIIssssffff',data, 48)
    try:
        active=active.decode() # A=data active and valid or V=data not valid
        latitude_b=latitude_b.decode() # N=north or S=south
        longitude_b=longitude_b.decode() # E=east or W=west

    except UnicodeDecodeError as e:
        print("Skipping: garbage data. Error: %s." % str(e))
        return

    time=fix_time(hour,minute,second,year,month,day)
    latitude=fix_coordinates(latitude_b,latitude)
    longitude=fix_coordinates(longitude_b,longitude)
    speed=fix_speed(speed)

    #it seems that A indicate reception
    if active != 'A':
        print("Skipping: (%s) lost GPS satelite reception. Time: %s." % (active, time))
        return

    return (latitude,longitude,time,speed,course)


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
            gpx += "\t\t<trkpt lat=\"%f\" lon=\"%f\"><time>%s</time><speed>%f</speed><course>%f</course></trkpt>\n" % l
    gpx += '\t</trkseg></trk>\n'
    gpx += '</gpx>\n'
    return gpx

	
#prev_offset = 0
#read 4 bytes size + 4 bytes string
#check if string == 'moov'
#while not seek to offset = prev_offset + 4 bytes size
#if 'moov' found
#prev_offset = next_after_moov
#read 4 bytes size + 4 bytes string
#check if string == 'gps '
#while not seek to offset = prev_offset + 4 bytes size
#if 'gps ' found looking offsets on gps data
def process_file(in_file):
    global gps_data
    global CounterGPSChunk
    global CounterSkipLostGPSChunk
    global CounterValidGPSChunk
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

                    if sub_atom_type == 'gps ':
                        print("Found gps chunk descriptor atom...")
                        gps_offset = 16 + sub_offset # +16 = skip headers
                        f.seek(gps_offset,0)
                        while gps_offset < ( sub_offset + sub_atom_size):
                            CounterGPSChunk += 1
                            gps_data.append(get_gps_atom(get_gps_atom_info(f.read(8)),f))
                            #do not add (remove) empty data when GPS data is not valid
                            if gps_data[len(gps_data)-1] is None:
                                CounterSkipLostGPSChunk += 1
                                del gps_data[len(gps_data)-1]
                            else:
                                CounterValidGPSChunk += 1
                                
                            gps_offset += 8
                            f.seek(gps_offset,0)
#                    else:
#                        print("gps chunk not found but %s" % sub_atom_type)
                    sub_offset += sub_atom_size
                    f.seek(sub_offset,0)

            offset += atom_size
            f.seek(offset,0)
    f.close()


def fnd(fname, s, start=0):
    with open(fname, 'rb') as f:
        fsize = os.path.getsize(fname)
        bsize = 4096
        buffer = None
        if start > 0:
            f.seek(start)
        overlap = len(s) - 1
        while True:
            if (f.tell() >= overlap and f.tell() < fsize):
                f.seek(f.tell() - overlap)
            buffer = f.read(bsize)
            if buffer:
                pos = buffer.find(s)
                if pos >= 0:
                    return f.tell() - (len(buffer) - pos)
            else:
                return -1


def searching_freeGPS_text(in_file):
    global CounterFreeGPS
    i = fnd(in_file, 'freeGPS ', 0)
    while i != -1:
        print("Found freeGPS at %x" % i)
        CounterFreeGPS += 1
        gps_chunk_offsets.append(i - 4) # 4 bytes before 'freeGPS ' = gps chunk size
        i = fnd(in_file, 'freeGPS ', i+9)

def hlp(i, bytes):
    atom_size,nop=struct.unpack_from('>II',bytes) # read 8 cause result '>I' is tuple => error
    return int(i),int(atom_size)

#universal way to find GPS data - looking for 'freeGPS ' as tag for gps chunks
#longer but should find GPS data at any files
def process_file_wo_gps_chunk(in_file):
    global gps_data
    global CounterSkipLostFreeGPS
    global CounterValidFreeGPS
    print("Processing file '%s'..." % in_file)
    searching_freeGPS_text(in_file)

    with open(in_file, 'rb') as f:
        for i in gps_chunk_offsets:
            f.seek(i)
            r = hlp(i,f.read(8)) #hack, need only 4 bytes
            gps_data.append(get_gps_atom(r,f))
            #do not add (remove) empty data when GPS data is not valid
            if gps_data[len(gps_data)-1] is None:
                CounterSkipLostFreeGPS += 1
                del gps_data[len(gps_data)-1]
            else:
                CounterValidFreeGPS += 1
                
    f.close()

def main():
    in_files,out_file=get_args()
    global gps_chunk_offsets
    global gps_data
    
    for f in in_files:
        #clear arrays from prev file
        #del gps_chunk_offsets[:]
        #del gps_data[:]
        
        process_file(f)
        if(len(gps_data) == 0):
            print("Found - Total GPS chunks:%d Valid:%d Skip:%d" % (CounterGPSChunk, CounterValidGPSChunk, CounterSkipLostGPSChunk))
            print("Can`t find GPS chunks at file %s, try direct searching.\r\n" % f)
            process_file_wo_gps_chunk(f) #try find GPS data directly

    gpx=get_gpx(gps_data,out_file)
    print("Found - Total GPS chunks:%d Valid:%d Skip:%d" % (CounterGPSChunk, CounterValidGPSChunk, CounterSkipLostGPSChunk))
    print("Found - Total freeGPS   :%d Valid:%d Skip:%d" % (CounterFreeGPS, CounterValidFreeGPS, CounterSkipLostFreeGPS))
    print("Found %d GPS valid data points." % len(gps_data))
    if gpx and len(gps_data) > 0 :
        with open (out_file, "w") as f:
            print("Wiriting data to output file '%s'." % out_file)
            f.write(gpx)
            f.close()
    else:
        print("GPS data not found.")
        sys.exit(1)

    print("Success!")
    
if __name__ == "__main__":
    main()
