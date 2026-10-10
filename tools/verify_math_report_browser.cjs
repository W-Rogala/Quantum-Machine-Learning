/* Browser QA for the mathematical report; records screenshots and evidence. */
let playwright;try{playwright=require(process.env.PLAYWRIGHT_MODULE||'playwright')}catch(e){if(process.env.PLAYWRIGHT_MODULE)throw e;playwright=require('C:/Users/wroga/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')}
const {chromium}=playwright;
const fs=require('fs');const path=require('path');
const root=path.resolve(__dirname,'..');const out=path.join(root,'output','math_report_qa');fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.REPORT_BROWSER_CHANNEL?{channel:process.env.REPORT_BROWSER_CHANNEL}:process.platform==='win32'?{channel:'msedge'}:{})});
 const page=await browser.newPage({viewport:{width:1440,height:1100}});
 const errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
 const url=process.argv[2]||'http://127.0.0.1:4188/';
 if(url.startsWith('file:'))await page.route(/^https?:\/\//,route=>route.abort());
 await page.goto(url,{waitUntil:'networkidle'});await page.locator('.qml-math').waitFor();
 const counts=await page.locator('.report-counts').textContent();
 await page.screenshot({path:path.join(out,'01_scope.png'),fullPage:false});
 await page.evaluate(()=>location.hash='chapter-01');await page.waitForTimeout(550);
 await page.screenshot({path:path.join(out,'02_math.png'),fullPage:false});
 const mathCount=await page.locator('.katex').count();
 const a=page.locator('a[href^="#term-"]').first();await a.hover();await page.locator('#math-tooltip').waitFor();
 const tooltip=await page.locator('#math-tooltip').textContent();await page.keyboard.press('Escape');
 await a.click();await page.waitForTimeout(450);const glossaryOK=await page.locator('.glossary-entry.selected').count();
 await page.locator('.qml-math nav a[href="#code-browser"]').click();await page.locator('#code-browser .source-code').waitFor();const codeTabOK=await page.locator('#code-browser').count();
 await page.evaluate(()=>location.hash='chapter-03');await page.waitForTimeout(450);
 const codeLink=page.locator('.math-chapter a[href^="#code-"]').first();const codeHash=await codeLink.getAttribute('href');await codeLink.click();await page.waitForTimeout(500);
 const codeOK=await page.locator('.highlight-line').count();await page.screenshot({path:path.join(out,'03_code.png')});
 await page.evaluate(()=>location.hash='comparisons');await page.waitForTimeout(950);
 const plotTitles=await page.locator('.comparison-chart').count();const svgs=await page.locator('#comparisons svg').count();
 const chartsText=await page.locator('#comparisons').textContent();await page.screenshot({path:path.join(out,'04_comparisons.png')});
 const filters=page.locator('#comparisons>label select');await filters.nth(0).selectOption('classical');await page.waitForTimeout(350);
 const classical=await page.locator('#comparisons').textContent();
 await page.evaluate(()=>location.hash='relations');await page.waitForTimeout(450);await page.locator('.graph-edge-list button').first().click();
 const graphDetail=await page.locator('.relation-detail').textContent();
 await page.screenshot({path:path.join(out,'05_graph.png')});
 const graphLayers={};for(const layer of ['project','theory','curated','imports']){await page.locator('#relations>label select').first().selectOption(layer);await page.waitForTimeout(220);graphLayers[layer]=await page.locator('.graph-edge-list button').count();}
 await page.evaluate(()=>location.hash='bibliography');await page.waitForTimeout(450);const bibliographyCount=await page.locator('.bib-entry').count();
 await page.evaluate(()=>location.hash='hypotheses');await page.waitForTimeout(350);const hypothesesCount=await page.locator('.hypothesis-entry').count();
 await page.evaluate(()=>location.hash='all-chapters');await page.waitForTimeout(900);
 const chapterCount=await page.locator('.math-chapter').count();const domIds=await page.evaluate(()=>{const ids=[...document.querySelectorAll('.qml-math [id]')].map(n=>n.id);return ids.filter((id,i)=>ids.indexOf(id)!==i)});
 const missingAnchors=await page.evaluate(()=>[...document.querySelectorAll('.math-chapter a[href^="#eq-"]')].map(a=>a.getAttribute('href').slice(1)).filter(id=>!document.getElementById(id)));
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>location.hash='chapter-01');await page.waitForTimeout(400);await page.screenshot({path:path.join(out,'06_mobile.png')});
 const mobileOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+2);
 const remote=requests.filter(u=>/^https?:/.test(u)&&!/^http:\/\/127\.0\.0\.1:4188\//.test(u));
 const result={url,counts,mathCount,tooltip,glossaryOK,codeTabOK,codeHash,codeOK,plotSections:plotTitles,plotSVGs:svgs,emptyPlot:chartsText.includes('No data'),classicalVisible:classical.toLowerCase().includes('svm'),graphDetail,graphLayers,bibliographyCount,hypothesesCount,chapterCount,duplicateIds:[...new Set(domIds)],missingAnchors:[...new Set(missingAnchors)],mobileOverflow,errors,remoteRequests:remote};
 fs.writeFileSync(path.join(out,url.startsWith('file:')?'browser_offline.json':'browser_preview.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));await browser.close();
 if(errors.length||domIds.length||missingAnchors.length||mobileOverflow||mathCount<1||codeOK<1||glossaryOK!==1||codeTabOK!==1||chapterCount!==12||svgs<11||hypothesesCount!==21||!result.classicalVisible||(url.startsWith('file:')&&remote.length))process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
