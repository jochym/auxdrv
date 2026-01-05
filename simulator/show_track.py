from matplotlib import pylab as plt
import numpy as np
import sys
from scipy.ndimage import median_filter
from scipy.interpolate import UnivariateSpline

def med(vec):
    m = 0

    r = []
    for nextElt in vec:
        if m > nextElt:
            m -= 1
        elif m < nextElt:
            m += 1
        r.append(m)
    return np.asarray(r)
    


STEPS=2**24
ARCSEC_PER_STEP = 360 * 60 * 60 / STEPS
deg = 1
# ARCSEC_PER_STEP = 1
sht = 0
# sht = 2800
while True:
    with open(sys.argv[1]) as f:
        tr = np.asarray([l.strip().split()[-6:-1] for l in f if '[DEBUG] Tracking AL Now' in l]).T
        print(tr[:,-1])
        al_tr = np.asarray([[float(v) for v in tr[2]], [float(v) for v in tr[4]], [float(v) for v in tr[0]]])[:,sht:]

    with open(sys.argv[1]) as f:
        tr = np.asarray([l.strip().split()[-6:-1] for l in f if '[DEBUG] Tracking AZ Now' in l]).T
        print(tr[:,-1])
        az_tr = np.asarray([[float(v) for v in tr[2]], [float(v) for v in tr[4]], [float(v) for v in tr[0]]])[:,sht:]

    datlen = min(al_tr.shape[1], az_tr.shape[1])
    az_tr = az_tr[:,:datlen]
    al_tr = al_tr[:,:datlen]

    al_tr_m = median_filter(al_tr[0], 3, mode='constant', cval=0)
    az_tr_m = median_filter(az_tr[0], 3, mode='constant', cval=0)

    day = 86400
    x = np.linspace(0, datlen, 300)/day

    # plt.figure(figsize=(18,6))
    fig, axs = plt.subplots(3, 1, sharex=True, height_ratios=[4,2,2], figsize=(18,12))
    plt.sca(axs[0])

    last_az, last_al = az_tr[0, -1], al_tr[0, -1]
    rang_az = -1
    rang_al = -1
    for i in range(1, datlen):
        if abs(al_tr_m[-i] - last_al) > 100:
            break
        rang_al = i
        last_al = al_tr_m[-i]
    if rang_al == -1:
        rang_al = datlen

    for i in range(1, datlen):
        if abs(az_tr_m[-i] - last_az) > 100:
            break
        rang_az = i
        last_az = az_tr_m[-i]
    if rang_az == -1:
        rang_az = datlen

    # rang_az = 2*rang_al 
    # print(al_tr.shape, az_tr.shape)
    alt = ARCSEC_PER_STEP * al_tr[:,-rang_al:]
    az = ARCSEC_PER_STEP * az_tr[:,-rang_az:]
    t = np.arange(datlen)
    # print(alt[:,0])
    # print(az[:,0])
    alt_fit = np.polyfit(t[-rang_al:], ARCSEC_PER_STEP * al_tr[0][-rang_al:], deg)
    az_fit = np.polyfit(t[-rang_az:], ARCSEC_PER_STEP * az_tr[0][-rang_az:], deg)
    # plt.plot(alt[0], '-', label=f'Alt RMS={alt[0].std():.2f} arcsec ({range/60:.2f}min)')
    # plt.plot(az[0], '-', label=f'AZ RMS={az[0].std():.2f} arcsec ({range/60:.2f}min)')
    # plt.plot(t, np.polyval(alt_fit, t), label=f'Alt: {alt_fit[0]:8.4g} arcsec/s')
    # plt.plot(t, np.polyval(az_fit, t), label=f'Az: {az_fit[0]:8.4g} arcsec/s')
    print(f'Tracking rate Alt: {al_tr[1, -1]/1024:8.4g} ; Az: {az_tr[1,-1]/1024:8.4g}  arcsec/s') 
    # plt.plot(ARCSEC_PER_STEP * al_tr_m[-range:], '-', label=f'Alt median RMS={(ARCSEC_PER_STEP * al_tr_m[-range:]).std():.2f} arcsec ({range/60:.2f}min)')
    # plt.plot(ARCSEC_PER_STEP * az_tr_m[-range:], '-', label=f'AZ median RMS={(ARCSEC_PER_STEP * az_tr_m[-range:]).std():.2f} arcsec ({range/60:.2f}min)')
    skew_rate_al = np.polyfit(t[-rang_al:], ARCSEC_PER_STEP * al_tr[0][-rang_al:], 1)[0]
    skew_rate_az = np.polyfit(t[-rang_az:], ARCSEC_PER_STEP * az_tr[0][-rang_az:], 1)[0]
    
    alt_drift = skew_rate_al*np.arange(datlen)
    az_drift = skew_rate_az*np.arange(datlen)

    print('Alt:', skew_rate_al, 'arcsec/s', skew_rate_al * (60*60), 'arcsec/h drift' )
    print('Az:', skew_rate_az, 'arcsec/s', skew_rate_az * (60*60), 'arcsec/h drift' )

    plt.plot(ARCSEC_PER_STEP * (al_tr[0]), '.', label='Alt (raw)')
    plt.plot(ARCSEC_PER_STEP * (az_tr[0]), '.', label='AZ (raw)')

    # plt.plot(ARCSEC_PER_STEP * (al_tr[0,0]+az_drift), '-', label='Alt clock skew')
    # plt.plot(ARCSEC_PER_STEP * (az_tr[0,0]+az_drift), '-', label='AZ Clock skew')
    # plt.plot(ARCSEC_PER_STEP * (al_tr[0]-az_drift), '.', label='Alt clock corrected', ms=1)
    # plt.plot(ARCSEC_PER_STEP * (az_tr[0]-az_drift), '.', label='AZ clock corrected', ms=1)

    xs = 7
    x0 = 43200/day
    # x0 = 33132/day
    x0 = 14039/day
    az_a = 280
    al_a = 140
    az_a = 210
    al_a = 60

    def fun(x):
        ''' x in [0,1)'''

        return np.sin(np.pi*x)


    def az_model(t):
        return np.polyval(az_fit, t)
        return az_fit[1] + t*skew_rate_az 
        return ARCSEC_PER_STEP * (az_tr[0,0]) + t*skew_rate_az # + az_a/((xs*fun(t/day-x0))**2 + 1) + az_a/((xs*fun(-x0))**2 + 1)

    def alt_model(t):
        return np.polyval(alt_fit, t)
        return alt_fit[1] + t*skew_rate_al
        return ARCSEC_PER_STEP * (al_tr[0,0]) + t*skew_rate_al # + al_a*(np.arctan(xs*(t/day-x0))+np.pi/2)/np.pi + 71*np.heaviside(t/day-x0, 1)

    # plt.plot(datlen*x, ARCSEC_PER_STEP * (az_tr[0,0]) + datlen*x*skew_rate, '-', label='Az skew')
    
    x_al = np.arange(datlen)[-rang_al:]/day
    x_az = np.arange(datlen)[-rang_az:]/day

    # plt.plot(day*x_al, alt_model(day*x_al), '-', label='Alt model')
    # plt.plot(day*x_az, az_model(day*x_az), '-', label='Az model')

    plt.plot(ARCSEC_PER_STEP * (al_tr_m), '-', label='Alt (median filtered)')
    plt.plot(ARCSEC_PER_STEP * (az_tr_m), '-', label='AZ (median filtered)')

    plt.axvspan(datlen-rang_al, datlen, color='grey', alpha=0.15)
    plt.axvspan(datlen-rang_az, datlen, color='grey', alpha=0.15)

    plt.legend()
    plt.ylabel(f'Tracking error (arcsec) \n {STEPS / (360 * 60 * 60) :.4f} steps/arcsec')
    plt.grid()
    plt.title(f'Drift over last {rang_az/60:.0f}/{rang_al/60:.0f} min.: Az: {skew_rate_az * (60*60):.2f} arcsec/h ; Alt: {skew_rate_al * (60*60):.2f} arcsec/h')

    plt.sca(axs[1])

    dat = ARCSEC_PER_STEP * al_tr[0][-rang_al:]
    spl_al = UnivariateSpline(day*x_al, dat)
    spl_al.set_smoothing_factor(0.5)
    dat = dat - spl_al(day*x_al)
    plt.plot(day*x_al, dat, '.', label=f'Alt model RMS:{dat.std():.2f} arcsec')
    dat = ARCSEC_PER_STEP * az_tr[0][-rang_az:]
    spl_az = UnivariateSpline(day*x_az, dat)
    spl_az.set_smoothing_factor(0.5)
    dat = dat - spl_az(day*x_az)
    plt.plot(day*x_az, dat, '.', label=f'Az model RMS:{dat.std():.2f} arcsec')

    plt.axvspan(datlen-rang_az, datlen, color='grey', alpha=0.15)
    plt.axvspan(datlen-rang_al, datlen, color='grey', alpha=0.15)

    plt.legend()
    plt.ylabel(f'Model residuals (arcsec) \n {STEPS / (360 * 60 * 60) :.4f} steps/arcsec')
    plt.grid()
    plt.sca(axs[2])

    plt.plot(al_tr[1]/1024, '-', label='Alt rate')
    plt.plot(az_tr[1]/1024, '-', label='AZ rate')
    # plt.plot(360*al_tr[2]/2**24, '-', label='Alt (degs)')
    # plt.axhline(ls=':')
    # plt.axhline(-15, ls='--')
    # plt.axhline(15, ls='--')
    plt.legend()
    plt.ylabel(f'Tracking rate\n(arcsec/s)')
    plt.xlabel('Time (s)')
    plt.grid()
    
    fig.tight_layout()
    plt.show()
