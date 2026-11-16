param([string[]]$Files)
Add-Type -TypeDefinition @"
using System; using System.IO; using System.Text; using System.Collections.Generic;
public static class Outb2 {
  public static string Stats(string path){
    var br = new BinaryReader(File.OpenRead(path));
    short fid = br.ReadInt16(); short clen = 10;
    if (fid == 4) clen = br.ReadInt16();
    int nc = br.ReadInt32(); int nt = br.ReadInt32();
    double t1, dt; double tscl=0, toff=0;
    if (fid == 1) { tscl = br.ReadDouble(); toff = br.ReadDouble(); t1 = 0; dt = 0; }
    else { t1 = br.ReadDouble(); dt = br.ReadDouble(); }
    var scl = new float[nc]; var off = new float[nc];
    for (int i=0;i<nc;i++) scl[i]=br.ReadSingle();
    for (int i=0;i<nc;i++) off[i]=br.ReadSingle();
    int ld = br.ReadInt32(); br.ReadBytes(ld);
    var names = new List<string>();
    for (int i=0;i<=nc;i++) names.Add(Encoding.ASCII.GetString(br.ReadBytes(clen)).Trim());
    for (int i=0;i<=nc;i++) br.ReadBytes(clen);
    if (fid == 1) br.ReadBytes(4*nt);
    int ip = names.IndexOf("GenPwr")-1, ib = names.IndexOf("BldPitch1")-1, iw = names.IndexOf("Wind1VelX")-1;
    double sw=0, sww=0, swmin=1e9, swmax=-1e9, sb=0, sbb=0; int nw=0;
    double se=0, s=0; int n=0; double seT=0, sT=0; int nT=0; double minP=1e9, maxP=-1e9;
    var rowbuf = new byte[2*nc];
    for (int k=0;k<nt;k++){
      br.Read(rowbuf,0,2*nc);
      double t = t1 + k*dt;
      double p = (BitConverter.ToInt16(rowbuf,2*ip)-off[ip])/scl[ip];
      if (t>=100.0 && t<=300.0){ double w=(BitConverter.ToInt16(rowbuf,2*iw)-off[iw])/scl[iw]; double b=(BitConverter.ToInt16(rowbuf,2*ib)-off[ib])/scl[ib]; sw+=w; sww+=w*w; if(w<swmin)swmin=w; if(w>swmax)swmax=w; sb+=b; sbb+=b*b; nw++; se+=(p-22000)*(p-22000); s+=p; n++; if(p<minP)minP=p; if(p>maxP)maxP=p; }
      if (k>=nt-500){ seT+=(p-22000)*(p-22000); sT+=p; nT++; }
    }
    double mean=s/n;
    double wm=sw/nw, bm=sb/nw; return String.Format("wind100-300: mean={0:F2} std={1:F2} TI={2:F3} min={3:F2} max={4:F2} | pitch mean={5:F2} std={6:F3} || ",wm,Math.Sqrt(sww/nw-wm*wm),Math.Sqrt(sww/nw-wm*wm)/wm,swmin,swmax,bm,Math.Sqrt(sbb/nw-bm*bm)) + String.Format("fid={0} nc={1} nt={2} t1={3} dt={4} | 100-300s: MSE={5:F1} kW2, mean={6:F1}, min={7:F1}, max={8:F1}, std={9:F1} | last500: MSE={10:F2}, mean={11:F1}, span={12:F3}s",
      fid,nc,nt,t1,dt,se/n,mean,minP,maxP,Math.Sqrt(se/n-(mean-22000)*(mean-22000)),seT/nT,sT/nT,500*dt);
  }
}
"@
foreach ($f in $Files) { Write-Output ("{0}: {1}" -f (Split-Path $f -Leaf), [Outb2]::Stats($f)) }
