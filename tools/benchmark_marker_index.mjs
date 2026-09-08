// Standalone CPU index study: node tools/benchmark_marker_index.mjs [spatial.js].
import {readFileSync} from 'node:fs';
import {compileFunction} from 'node:vm';
import {performance} from 'node:perf_hooks';
const source=process.argv[2]||'src/inklet/experimental/scene_viewer/spatial.js';
const MarkerIndex=compileFunction(readFileSync(source,'utf8')+'\nreturn MarkerIndex;')();
const median=a=>[...a].sort((a,b)=>a-b)[Math.floor(a.length/2)];
const results=[];
for(const count of [250000,1000000]){
 const records=new DataView(new ArrayBuffer(count*36));let seed=7182;
 const random=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return (seed>>>0)/4294967296;};
 for(let k=0;k<count;k++){records.setFloat64(k*36,random()*200-100,true);records.setFloat64(k*36+8,random()*200-100,true);records.setFloat64(k*36+16,.1+random()*.3,true);}
 const batch={count,records,bounds:[-.5,-.5,.5,.5]};
 const start=performance.now(),index=new MarkerIndex(batch),build_ms=performance.now()-start,queries=[];
 for(const [name,size] of [['tiny',1],['zoom',50],['broad',150],['full',210]]){
  const samples=[];let candidates,checksum;
  for(let k=0;k<20;k++){
   const x=-size/2+(k%3)*.01,y=-size/2+(k%5)*.01,t=performance.now(),selected=index.query([x,y,size,size]);
   const elapsed=performance.now()-t;candidates=selected===null?count:selected.length;checksum=selected===null?null:[selected[0],selected.at(-1)];
   if(k>=5)samples.push(elapsed);
  }
  queries.push({name,size,candidates,checksum,median_ms:median(samples),samples_ms:samples});
 }
 results.push({count,build_ms,retained_index_bytes:index.bytes,queries});
}
console.log(JSON.stringify({runtime:process.version,platform:process.platform,source,results},null,2));
