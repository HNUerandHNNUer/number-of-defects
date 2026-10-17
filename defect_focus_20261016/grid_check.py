from fixed_scan import *
if __name__=='__main__':
 inv=pd.read_csv(ROOT/'mips_analysis_20261014/trajectory_inventory.csv');rows=[]
 for level in (4,5,6):
  v,g=mesh(level)
  for n in (100,350):
   j=inv[(inv.n==n)&(inv.F==10)].iloc[0]
   for step in (50000000,75000000,100000000):
    a=np.loadtxt(str(Path(j.coordinate_directory)/('defect_out-%010d.xyz'%step)),skiprows=2);x=a[a[:,0]==1,1:4]
    for h in (1.5,3.):
     r=detect(x,v,g,h);rows.append(dict(n=n,level=level,h=h,step=step,Nplus=r['Nplus'],Nminus=r['Nminus'],fallback=r['fallback']))
   print('GRID',level,n,flush=True)
 pd.DataFrame(rows).to_csv(OUT/'grid_convergence.csv',index=False)
