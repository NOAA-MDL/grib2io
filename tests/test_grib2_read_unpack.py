import grib2io

if __name__  == '__main__':
    g = grib2io.open('./data/gfs.t00z.pgrb2.1p00.f024')
    for msg in g:
        msg.data
    g.close()
