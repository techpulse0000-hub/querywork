// Headless app regression check; does not control the user's browser.
const {chromium}=require('C:/Users/jezzc/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1280,height:900}});
  const token=fs.readFileSync(path.resolve('data/api-token'),'utf8').trim();
  const api=async(route,body)=>{
   const r=await context.request.fetch('http://127.0.0.1:8766/api/v1'+route,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token},data:body});
   if(!r.ok())throw Error('App API returned '+r.status());return r.json();
  };
  const e=await api('/experiments',{original_search:'Research upgrade UI check',outcome:'Fictional demo for checking round outcome review display',requirements:['Demo requirement'],mode:'demo'});
  const j=await api('/experiments/'+e.id+'/optimize',{idempotency_key:'ui-check',batch_size:5,max_queries:10,max_rounds:2,target_score:100});
  for(let i=0;i<12000;i++){const job=await api('/jobs/'+j.id);if(!['queued','running'].includes(job.status)){if(job.status!=='complete')throw Error('Demo failed');break;}await new Promise(r=>setTimeout(r,100));}
  const page=await context.newPage();await page.goto('http://127.0.0.1:8766/');
  await page.getByRole('button',{name:/^History/}).click();
  await page.getByRole('button',{name:/^Research upgrade UI check Fictional/}).first().click();
  await page.getByRole('heading',{name:'Round outcome checks'}).waitFor();
  const reviews=page.locator('.round-outcome-reviews');
  await reviews.locator(':scope > details').first().locator('summary').first().click();
  if(!await reviews.getByText('Demo only; real evidence requires live search.').first().isVisible())throw Error('Review body missing');
  if(!await reviews.getByText(/advanced-search-techniques.pdf/).first().isVisible())throw Error('Reference provenance missing');
  await reviews.screenshot({path:path.resolve('../querywork-research-review-desktop.png')});
  await page.setViewportSize({width:390,height:844});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1))throw Error('Mobile horizontal overflow');
  await reviews.screenshot({path:path.resolve('../querywork-research-review-mobile.png')});
  console.log(JSON.stringify({desktop:'passed',mobile:'passed',experiment_id:e.id,review_sections:await reviews.locator(':scope > details').count()}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
