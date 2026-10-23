"""T3.5f route analysis 2c: direction and size of the FAST-LIVO2-minus-reference error against the robot velocity. usage (in the route dir): err_vs_velocity.py [ref_prefix]; needs deg_*.csv and ref_*.csv"""
import sys, numpy as np
PFX = sys.argv[1] if len(sys.argv) > 1 else "ref"
for l in ("run1","run2"):
    r=np.genfromtxt("%s_%s.csv"%(PFX,l),delimiter=",",names=True); d=np.genfromtxt("deg_%s.csv"%l,delimiter=",",names=True)
    ok=r["accepted"]==1; rows=[]
    for i in np.where(ok)[0]:
        t=r["t_s"][i]; k=np.searchsorted(d["t_s"],t); lo,hi=max(k-2,0),min(k+2,len(d["t_s"])-1)
        v=np.array([d["x"][hi]-d["x"][lo],d["y"][hi]-d["y"][lo]])/(d["t_s"][hi]-d["t_s"][lo]); sp=np.hypot(*v)
        e=np.array([r["err_x"][i],r["err_y"][i]])
        if sp>0.05: rows.append((t,sp,np.hypot(*e),e@v/(sp*np.hypot(*e)+1e-9),e@v/sp**2, (e[0]*v[1]-e[1]*v[0])/(sp**2)))
    a=np.array(rows); print(l,"moving windows",len(a))
    print("  speed m/s median %.2f; |err| median %.3f; cos(err,velocity) median %.2f (1=along, 0=sideways); err/speed along-track median %+.2f s; cross-track %+.2f s"%(np.median(a[:,1]),np.median(a[:,2]),np.median(a[:,3]),np.median(a[:,4]),np.median(a[:,5])))
    print("  corr(|err|, speed) %.2f; cos values:"%np.corrcoef(a[:,1],a[:,2])[0,1], a[:,3].round(1))
