export async function api(path,body,key){
 let response;
 try{response=await fetch('/api/v2/'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json',...(key?{'Idempotency-Key':key}:{})},body:JSON.stringify(body)});}catch{throw Error('Cannot reach the dashboard. Please check that it is running on this computer.');}
 const data=await response.json();if(!response.ok)throw Error(data.error||'Could not save. Please try again.');return data;
}
export async function attach(file,site,visit,options={}){
 if(file.size>25*1024*1024)throw Error(file.name+' is larger than 25 MB. Choose a smaller file; the visit draft is saved.');
 const query=new URLSearchParams({site_id:site,name:file.name,...(visit?{visit_id:visit}:{}),...options});let response;
 try{response=await fetch('/api/v2/attachments/binary?'+query,{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file})}catch{throw Error('The photo upload was interrupted. Your draft is saved. Check the dashboard connection, then retry the file.');}
 let result;try{result=await response.json()}catch{throw Error('The server did not finish the file upload. Your draft is saved; please retry.');}
 if(!response.ok)throw Error(result.error||'The file could not be saved. Please retry.');return result;
}
