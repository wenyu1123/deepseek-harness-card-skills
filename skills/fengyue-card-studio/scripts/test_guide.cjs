/* Observable guide behavior only. Does not certify Fengyue server sanitization. */
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const args=Object.fromEntries(process.argv.slice(2).reduce((pairs,v,i,a)=>{if(v.startsWith('--'))pairs.push([v.slice(2),a[i+1]]);return pairs;},[]));
if(!args.file||!args.out)throw Error('Use --file preview.html --out report-dir [--playwright-dir path] [--browser executable]');
const {chromium}=require(args['playwright-dir']||'playwright');
const source=fs.readFileSync(path.resolve(args.file),'utf8'),out=path.resolve(args.out);fs.mkdirSync(out,{recursive:true});
const server=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html; charset=utf-8');res.end(source);});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin=`http://127.0.0.1:${server.address().port}`;
 const browser=await chromium.launch({headless:true,...(args.browser?{executablePath:args.browser}:{})});
 const reports=[];
 try{
  for(const width of [320,390,1280]){
   const context=await browser.newContext({viewport:{width,height:1000}}),page=await context.newPage();
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto(origin);const root=page.locator('.fy-guide');await page.waitForSelector('.fy-guide[data-ready="true"]');
   assert.equal(await root.locator('a').count(),0);
   assert.equal(await root.locator('[data-panel]:visible').count(),1);
   await page.screenshot({path:path.join(out,`首屏-${width}.png`),fullPage:true});
   await root.locator('[data-tab="1"]').click();await root.locator('.fy-person summary').first().click();assert(await root.locator('.fy-person-body').first().isVisible());
   await root.locator('[data-tab="2"]').click();
   const controls=root.locator('[data-input]');assert(await controls.count()>=7,'Need separate name/age/identity/appearance/personality/history/relations fields');
   const values=[];
   for(let i=0;i<await controls.count();i++){
    const el=controls.nth(i),type=await el.evaluate(e=>e.tagName==='SELECT'?'select':e.type);
    let value=type==='number'?'27':`测试资料${i}：<标签>&引号"`;
    if(type==='select'){value=await el.locator('option').nth(1).getAttribute('value');await el.selectOption(value);}else await el.fill(value);
    values.push(value);
   }
   const colCount=await root.locator('.fy-fields').first().evaluate(e=>getComputedStyle(e).gridTemplateColumns.split(' ').length);
   assert.equal(colCount,width<540?1:2);
   await page.screenshot({path:path.join(out,`分栏人设-${width}.png`),fullPage:true});
   const extras=await root.locator('[data-add-person]').count();
   if(extras){await root.locator('[data-add-person]').click();await root.locator('[data-extra-person] [data-person-field="name"]').fill('临时角色甲');}
   await root.locator('[data-tab="3"]').click();
   const choices=root.locator('[data-opening]'),selected=Math.min(1,(await choices.count())-1);await choices.nth(selected).check();
   await root.locator('[data-generate]').click();let generated=await root.locator('[data-output]').inputValue();
   for(const value of values)assert(generated.includes(value),'Filled field missing from output');
   const cfg=JSON.parse(await root.locator('[data-config]').textContent());
   assert(generated.includes(cfg.openings[selected].text));for(let i=0;i<cfg.openings.length;i++)if(i!==selected&&cfg.openings[i].text!==cfg.openings[selected].text)assert(!generated.includes(cfg.openings[i].text));
   await page.evaluate(()=>{Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{window.__copy=text;}}})});
   await root.locator('[data-copy]').click();assert.equal(await page.evaluate(()=>window.__copy),generated);
   if(extras){await root.locator('[data-tab="2"]').click();await root.locator('[data-remove-person]').click();}
   else await root.locator('[data-tab="2"]').click();
   const firstText=root.locator('input[data-input]:not([type="number"]),textarea[data-input]').first();await firstText.fill('更新后的角色资料');
   await root.locator('[data-tab="3"]').click();await root.locator('[data-copy]').click();generated=await root.locator('[data-output]').inputValue();
   assert(generated.includes('更新后的角色资料'));assert(!generated.includes('临时角色甲'));assert.equal(await page.evaluate(()=>window.__copy),generated);
   await root.locator('[data-output]').fill(generated+'\n手工保留内容');
   await root.locator('[data-tab="2"]').click();await firstText.fill('又一次修改');await root.locator('[data-tab="3"]').click();await root.locator('[data-copy]').click();
   assert((await root.locator('[data-feedback]').textContent()).includes('先重新生成'));
   assert((await root.locator('[data-output]').inputValue()).includes('手工保留内容'));
   await root.locator('[data-generate]').click();
   await page.evaluate(()=>{Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw Error('denied')}}});document.execCommand=()=>false;});
   await root.locator('[data-copy]').click();assert((await root.locator('[data-feedback]').textContent()).includes('已选中完整开局'));
   assert(await root.locator('[data-output]').evaluate(e=>e.selectionStart===0&&e.selectionEnd===e.value.length));
   await page.screenshot({path:path.join(out,`开局结果-${width}.png`),fullPage:true});
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await root.locator('[data-tab="3"]').focus();await page.keyboard.press('ArrowLeft');assert(await root.locator('[data-panel="2"]').isVisible());
   assert.deepEqual(errors,[]);reports.push({width,fields:values.length,columns:colCount,generate:true,copyMock:true,copyDeniedSelection:true,staleCopyPrevented:true,removedPeopleAbsent:true,editedResultProtected:true,noOverflow:true});
   await context.close();
  }
  const context=await browser.newContext({viewport:{width:1280,height:1000}}),page=await context.newPage();await page.goto(origin);await page.waitForSelector('[data-ready="true"]');
  await page.evaluate(()=>document.querySelector('.fy-guide').style.width='350px');await page.locator('[data-tab="2"]').click();
  assert.equal(await page.locator('.fy-fields').first().evaluate(e=>getComputedStyle(e).gridTemplateColumns.split(' ').length),1);
  const stripped=source.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');await page.setContent(stripped);
  assert(await page.locator('[data-runtime-note]').isVisible());assert(await page.locator('[data-generate]').isDisabled());assert(await page.locator('[data-copy]').isDisabled());assert.equal(await page.locator('[data-panel]:visible').count(),4);
  await page.goto(origin);await page.waitForSelector('[data-ready="true"]');
  await page.evaluate(()=>{const clone=document.querySelector('.fy-guide').cloneNode(true);clone.removeAttribute('data-ready');document.body.append(clone);const program=[...document.querySelectorAll('script')].find(s=>s.textContent.includes('Each instance owns'));const rerun=document.createElement('script');rerun.textContent=program.textContent;document.body.append(rerun);});
  assert.equal(await page.locator('.fy-guide[data-ready="true"]').count(),2);
  const second=page.locator('.fy-guide').nth(1);await second.locator('[data-tab="2"]').click();assert(await page.locator('.fy-guide').first().locator('[data-panel="0"]').isVisible());
  assert.equal(await page.locator('[id]').evaluateAll(items=>new Set(items.map(e=>e.id)).size),await page.locator('[id]').count());
  await context.close();reports.push({narrowDesktopColumn:true,scriptUnavailableExplicit:true,independentInstances:true,uniqueAriaIds:true});
  fs.writeFileSync(path.join(out,'浏览器验收.json'),JSON.stringify({passed:true,reports,clipboardTest:'mocked success/denial; no system clipboard mutation',platformSaveVerified:false,visualReview:'screenshots require inspection'},null,2));
  console.log(JSON.stringify({passed:true,out,reports}));
 }finally{await browser.close();server.close();}
})().catch(error=>{fs.writeFileSync(path.join(out,'浏览器验收.json'),JSON.stringify({passed:false,error:String(error)},null,2));console.error(error);server.close();process.exitCode=1;});
