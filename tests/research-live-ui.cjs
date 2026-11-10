// Read-only rendered check of the completed live experiment.
const {chromium}=require('C:/Users/jezzc/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}});
  await page.goto('http://127.0.0.1:8766/');
  await page.getByRole('button',{name:/^History/}).click();
  await page.locator('.history-list').getByRole('button',{name:/^sport teams about to start their tournament.*2026-11-07/}).first().click();
  await page.getByRole('heading',{name:'Round outcome checks'}).waitFor();
  const reviews=page.locator('.round-outcome-reviews');
  if(await reviews.locator(':scope > details').count()!==2)throw Error('Expected two outcome checks');
  await reviews.locator(':scope > details').last().locator('summary').first().click();
  if(!await reviews.getByText(/review claims remain unverified/).last().isVisible())throw Error('Evidence warning missing');
  if(!await page.getByText('Best result retained · 60 / 100',{exact:true}).isVisible())throw Error('Retained score missing');
  await reviews.screenshot({path:path.resolve('../querywork-research-live-desktop.png')});
  await page.setViewportSize({width:390,height:844});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1))throw Error('Mobile overflow');
  await reviews.screenshot({path:path.resolve('../querywork-research-live-mobile.png')});
  console.log('Live evidence review and warnings visible; desktop/mobile passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
