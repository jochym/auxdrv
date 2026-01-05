from matplotlib import pylab as plt
import numpy as np
import sys

while True:
    with open(sys.argv[1]) as f:
        gr = np.asarray([[float(v) for v in " ".join(l.strip().split()[8:10])[2:-1].split()]
                            for l in f if 'Guiding' in l]).T



    # plt.plot(gr[0][-36000:], '-')
    # plt.plot(gr[1][-36000:], '-')
    plt.plot(gr[0], '-')
    plt.plot(gr[1], '-')
    plt.grid()
    plt.show()


plt.show()