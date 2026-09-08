'use strict';
// A packed grid of marker centers with conservative per-cell ink bounds.
// Each marker occurs once, even if a large marker spans many cells.
class MarkerIndex{
 constructor(batch){
  this.batch=batch;const view=batch.records,n=batch.count;
  let xmin=Infinity,ymin=Infinity,xmax=-Infinity,ymax=-Infinity;
  for(let k=0;k<n;k++){const x=view.getFloat64(k*36,true),y=view.getFloat64(k*36+8,true);xmin=Math.min(xmin,x);xmax=Math.max(xmax,x);ymin=Math.min(ymin,y);ymax=Math.max(ymax,y);}
  const side=Math.max(1,Math.min(128,Math.ceil(Math.sqrt(n/32)))),cells=side*side;
  const counts=new Uint32Array(cells),bins=new Uint32Array(n),bounds=new Float64Array(cells*4),unit=batch.bounds;
  for(let c=0;c<cells;c++)bounds.set([Infinity,Infinity,-Infinity,-Infinity],c*4);
  for(let k=0;k<n;k++){
   const o=k*36,x=view.getFloat64(o,true),y=view.getFloat64(o+8,true),size=view.getFloat64(o+16,true);
   const cx=xmax===xmin?0:Math.min(side-1,Math.floor((x-xmin)/(xmax-xmin)*side)),cy=ymax===ymin?0:Math.min(side-1,Math.floor((y-ymin)/(ymax-ymin)*side));
   const c=cy*side+cx,j=c*4;bins[k]=c;counts[c]++;
   bounds[j]=Math.min(bounds[j],x+unit[0]*size);bounds[j+1]=Math.min(bounds[j+1],y+unit[1]*size);
   bounds[j+2]=Math.max(bounds[j+2],x+unit[2]*size);bounds[j+3]=Math.max(bounds[j+3],y+unit[3]*size);
  }
  const offsets=new Uint32Array(cells+1),indices=new Uint32Array(n);
  for(let c=0;c<cells;c++)offsets[c+1]=offsets[c]+counts[c];
  const cursor=offsets.slice();for(let k=0;k<n;k++)indices[cursor[bins[k]]++]=k;
  this.bounds=bounds;this.offsets=offsets;this.indices=indices;
  this.bytes=bounds.byteLength+offsets.byteLength+indices.byteLength;
 }
 query(box){
  const [x,y,w,h]=box,right=x+w,bottom=y+h,found=[],view=this.batch.records,unit=this.batch.bounds;
  for(let c=0;c<this.offsets.length-1;c++){
   const j=c*4,b=this.bounds;
   if(b[j]>right||b[j+1]>bottom||b[j+2]<x||b[j+3]<y)continue;
   for(let p=this.offsets[c];p<this.offsets[c+1];p++){
    const k=this.indices[p],o=k*36,px=view.getFloat64(o,true),py=view.getFloat64(o+8,true),size=view.getFloat64(o+16,true);
    if(px+unit[0]*size<=right&&py+unit[1]*size<=bottom&&px+unit[2]*size>=x&&py+unit[3]*size>=y)found.push(k);
   }
  }
  // Spatial order must never replace source paint order.
  return found.length===this.batch.count?null:Uint32Array.from(found).sort();
 }
}
